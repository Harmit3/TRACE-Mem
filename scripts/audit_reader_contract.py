"""Inspect the exact answer/citation contract for the two historical schema errors."""

from argparse import ArgumentParser
from functools import lru_cache
import json
from pathlib import Path

from scripts.compare_local_verifiers import QWEN, SETTINGS, local_json
from scripts.replay_memora_full import recover_extraction
from scripts.run_memora import ARTIFACTS, ROOT, sha, write
from scripts.run_memora_failure_isolation import PRIOR, QWEN_DIGEST, reconstruct, response_snapshot
from scripts.run_t2_development import frozen_rows
from trace_mem.features_v3 import CachedMiniLM, V3Features, pinned_nli
from trace_mem.llm_tasks import LLMTasks
from trace_mem.providers import ChatProvider, ProviderConfig, ProviderError, http_transport
from trace_mem.training import load_model


def contract_fields(raw):
    detail = response_snapshot(raw)
    if detail["keys_valid"]:
        response = json.loads(raw["message"]["content"])
        answer = response["answer"]
        citations = response["citations"]
        detail["answer_kind"] = ("null" if answer is None else "other_type"
                                 if not isinstance(answer, str) else "text" if answer.strip() else "blank")
        detail["citation_count"] = len(citations) if isinstance(citations, list) else None
    detail.pop("citations", None)
    return detail


def run(source, prior, output, nli, outcomes):
    import torch

    if (ROOT / "results").resolve() not in output.resolve().parents or sha(
            prior / "predictions.json") != PRIOR:
        raise ValueError("Requires the pinned Step 24 run and ignored output")
    if {m["name"]: m["digest"] for m in local_json("/api/tags")["models"]}.get(QWEN) != QWEN_DIGEST:
        raise ValueError("The pinned Qwen reader is unavailable")
    _, _, events, prepared, queries, _ = recover_extraction(
        source, prior, json.loads((prior / "extraction-report.json").read_bytes()))
    cutoff = queries[0].observed_on
    events = tuple(e for e in events if e.observed_on <= cutoff)
    prepared = tuple(e for e in prepared if e.source.observed_on <= cutoff)
    torch.set_num_threads(4)
    mini = CachedMiniLM()

    @lru_cache(maxsize=4096)
    def one(text):
        return tuple(mini((text,))[0])

    def embed(texts):
        return [one(item) for item in texts]

    features = V3Features(embed, lru_cache(maxsize=2048)(pinned_nli(nli)))
    without = V3Features(embed)
    builders = {"T1": features, "T1-no-NLI": without, "T2": features, "H-paced": without}
    models = {m: load_model(ARTIFACTS / f) for m, f in (
        ("T1", "full.json"), ("T1-no-NLI", "no_nli.json"))}
    errors = reconstruct(prior, events, prepared, queries, json.loads(
        (prior / "predictions.json").read_bytes()), builders, models, frozen_rows(outcomes)["train"], embed)
    captures = []

    def transport(*args):
        raw = http_transport(*args)
        captures.append(contract_fields(raw))
        return raw

    backend = ChatProvider(ProviderConfig("ollama", QWEN, 2, **SETTINGS),
                           output / "contract-probe.sqlite", transport=transport)
    rows = []
    for (query, facts), reason in errors.values():
        if "task schema" not in reason:
            continue
        before = len(captures)
        try:
            LLMTasks(backend).answer_from_facts(query.text, facts, as_of=query.as_of)
        except ProviderError as exc:
            rows.append({"error": str(exc), "fields": captures[-1] if len(captures) > before else None})
        else:
            rows.append({"error": None, "fields": captures[-1] if len(captures) > before else None})
    result = {"outcomes": rows, "provider": backend.stats()}
    write(output / "contract-probe.json", result)
    return result


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    for name in ("source", "prior", "output", "nli", "outcomes"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.source, args.prior, args.output, args.nli, args.outcomes)))
