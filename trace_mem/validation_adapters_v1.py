"""Offline asset verification and local-only inference bindings for the reviewed runner."""

from contextlib import closing
from hashlib import file_digest
import json
from pathlib import Path
from urllib.request import urlopen

from trace_mem.controller import FEATURE_NAMES
from trace_mem.features_v3 import MINILM, MINILM_REVISION, NLI_REVISION, CachedMiniLM, V3Features, pinned_nli
from trace_mem.llm_tasks import DIRECT_V2_PROMPT, LLMTasks, RESPONSE_SCHEMAS
from trace_mem.memora_benchmark import Question
from trace_mem.providers import ChatProvider, LimitExceeded, ProviderConfig, ProviderError, http_transport
from trace_mem.reader_v2 import BUDGETS, PROMPT, TASK, read
from trace_mem.retrieval_diagnostic import trim
from trace_mem.validation_v2 import ExecutionPaused, frozen_rules, signature


ROOT = Path(__file__).resolve().parents[1]
QWEN = "qwen2.5:7b-instruct-q4_K_M"


def verify_contract(pins):
    if (pins["feature_order"] != list(FEATURE_NAMES) or pins["minilm_revision"] != MINILM_REVISION
            or pins["nli_revision"] != NLI_REVISION or pins["qwen_name"] != QWEN
            or pins["settings"] != {"seed": 23, "timeout": 120, "retries": 0, "max_input_tokens": 4096,
                                    "max_output_tokens": 256, "context_tokens": 4096}):
        raise ValueError("Feature order, model revision or generation configuration changed")
    for label, text, task in (("reader", PROMPT, TASK), ("verifier", DIRECT_V2_PROMPT, "verify-direct-v2")):
        if signature([text, RESPONSE_SCHEMAS[task]]) != pins[f"{label}_prompt_schema_sha256"]:
            raise ValueError(f"Frozen {label} prompt or schema differs")


def sha(path):
    with Path(path).open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def local_metadata(path):
    if path not in ("/api/tags", "/api/version"):
        raise ValueError("Only read-only Ollama metadata is supported")
    with closing(urlopen(f"http://127.0.0.1:11434{path}", timeout=10)) as response:
        return json.load(response)


def asset_check(pins, nli, outcomes, metadata=local_metadata):
    from huggingface_hub import try_to_load_from_cache

    verify_contract(pins)
    models = {row["name"]: row["digest"] for row in metadata("/api/tags")["models"]}
    if models.get(QWEN) != pins["qwen_sha256"] or metadata("/api/version")["version"] != pins["ollama_version"]:
        raise ValueError("Installed Ollama model or runtime differs from the frozen pins")
    for name, expected in pins["minilm_files"].items():
        resolved = try_to_load_from_cache(MINILM, name, revision=MINILM_REVISION)
        if not isinstance(resolved, str) or sha(resolved) != expected:
            raise ValueError(f"Missing or modified local MiniLM file {name}")
    for name, expected in pins["nli_files"].items():
        if sha(nli / name) != expected:
            raise ValueError(f"Modified NLI file {name}")
    for name, expected in pins["controllers"].items():
        if sha(ROOT / "docs/t1_v3_artifacts" / name) != expected:
            raise ValueError(f"Controller digest differs for {name}")
    if sha(outcomes) != pins["training_reference_sha256"]:
        raise ValueError("Frozen feature reference differs")
    return {"qwen": pins["qwen_sha256"], "minilm": MINILM_REVISION, "nli": NLI_REVISION,
            "verified_files": (len(pins["minilm_files"]) + len(pins["nli_files"])
                               + len(pins["controllers"]) + 1)}


class VerifierAdapter:
    """Keep LLMTasks serialization and capture same-request Ollama usage."""

    def __init__(self, config, response_parser, transport):
        self.config = config
        self.parse_response = response_parser
        self.transport = transport
        self.usage = None

    def generate(self, task, prompt, payload, validate):
        if task != "verify-direct-v2" or prompt != DIRECT_V2_PROMPT:
            raise ProviderError("Unexpected verifier prompt")
        if len((prompt + payload).encode()) + 128 > self.config.context_tokens - self.config.max_output_tokens:
            raise ProviderError("Input exceeds verifier allowance")
        url, headers, body = ChatProvider.request_for(self.config, task, prompt, payload)
        raw = self.transport(url, headers, body, self.config.timeout)
        text, sent, received, model, finished = self.parse_response(raw)
        self.usage = sent, received
        if (model != QWEN or not finished or received > self.config.max_output_tokens
                or sent + received > self.config.context_tokens):
            raise ProviderError("Verifier response failed model, completion or usage validation")
        validate(text)
        return text

    def __call__(self, claim, target, evidence):
        self.usage = None
        try:
            result = LLMTasks(self, verification_mode="direct-v2").verify(
                claim, target, conversation=(evidence,))
        except (ProviderError, ValueError, KeyError, TypeError):
            result = "invalid"
        return (result, *(self.usage or (None, None)))


def bind_reader(provider, embed):
    def invoke(question, index, cutoff):
        query = Question("fixture", "diagnostic", question, cutoff)
        handle = index.retrieve(question, cutoff, embed, k=8)
        context = trim(query, index.materialize(handle, "subject"), 3000, 8)
        try:
            return read(provider, question, context, as_of=cutoff, mode="short").answer
        except LimitExceeded as error:
            if str(error) == "Input exceeds conservative preflight ceiling":
                raise ProviderError(str(error)) from None
            raise ExecutionPaused("Reader resource limit reached") from error
    return invoke


def bind_features(embed, nli):
    full, reduced = V3Features(embed, nli), V3Features(embed)
    def bind(builder):
        def build(item, target, fraction):
            return builder(item.claim, target, entity="subject", source=item.source,
                           budget_remaining_fraction=fraction)
        return build
    return {"T2": bind(full), "T2-no-NLI": bind(reduced), "H-paced": bind(reduced)}


def train_reference(path):
    vectors = []
    for line in Path(path).read_bytes().splitlines():
        row = json.loads(line)
        if row["split"] == "train":
            vectors.extend(c["features"] for step in row["steps"] for c in step["candidates"]
                           if "features" in c)
    return vectors


def bind(pins, nli, outcomes, output, reader_limit, *, transport=http_transport):
    embed, infer = CachedMiniLM(), pinned_nli(nli)
    settings = pins["settings"]
    verifier = ChatProvider(ProviderConfig("ollama", QWEN, 0, **settings), output / "verifier-parser.sqlite")
    reader = ChatProvider(ProviderConfig("ollama", QWEN, reader_limit,
                          **(settings | {"max_output_tokens": BUDGETS["short"]})),
                          output / "reader.sqlite", transport=transport)
    root = ROOT / "docs/t1_v3_artifacts"
    names = ("full.json", "no_nli.json")
    rules = frozen_rules(*(root / name for name in names),
                         [pins["controllers"][name] for name in names], train_reference(outcomes))
    return rules, bind_features(embed, infer), VerifierAdapter(verifier.config, verifier._response, transport), bind_reader(reader, embed), reader
