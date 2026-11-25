"""Run the frozen, local-only Memora development subset or its plumbing smoke."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time

from scripts.compare_local_verifiers import MODE, QWEN, SETTINGS, checksum, local_json
from scripts.updateset_v2_pilot import PROMPT_SCHEMA, QWEN_DIGEST
from trace_mem.data.memora import replay
from trace_mem.context_extraction import contextual_prepare
from trace_mem.features_v3 import CachedMiniLM, MINILM_REVISION, NLI_REVISION, V3Features, pinned_nli
from trace_mem.llm_tasks import DIRECT_V2_PROMPT, LLMTasks, RESPONSE_SCHEMAS
from trace_mem.memora_benchmark import answer_suite, prepare, questions, run_suite
from trace_mem.providers import ChatProvider, ProviderConfig
from trace_mem.training import load_model

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/memora_step19_freeze.json"
ARTIFACTS = ROOT / "docs/t1_v3_artifacts"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(directory, *args):
    return subprocess.check_output(["git", "-C", str(directory), *args], text=True).strip()


def audit_checkout(directory, protocol):
    revision = protocol["revision"]
    if git(directory, "rev-parse", "HEAD") != revision or git(
            directory, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Use a clean checkout of the pinned Memora revision")
    subsets = [protocol["development"], *protocol["held_out"]]
    if len({Path(item["path"]).name for item in subsets}) != len(subsets):
        raise ValueError("Benchmark partitions must not share personas")
    for item in subsets:
        history = item["path"]
        rubric = f"{history}/evaluation_questions_{Path(history).name}.json"
        for path, expected in ((f"{history}/conversations", item["conversation_tree"]),
                               (rubric, item["rubric_blob"])):
            if git(directory, "rev-parse", f"{revision}:{path}") != expected:
                raise ValueError("Unexpected pinned subset object")
    return revision


def write(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes((json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode())
    temporary.replace(path)


def run(source, nli, output, *, smoke, extraction_validation=None):
    import torch
    import transformers

    if (ROOT / "results").resolve() not in output.resolve().parents:
        raise ValueError("Keep predictions and response caches under ignored results/")
    validated = None
    if extraction_validation is not None:
        design = ROOT / "docs/memora_step20_validation.json"
        validated = json.loads(extraction_validation.read_bytes())
        if (validated["protocol_sha256"] != sha(design) or validated["qwen_digest"] != QWEN_DIGEST
                or not validated["extractor_passes"]):
            raise ValueError("Contextual extractor has not passed the frozen development gate")
    protocol = json.loads(PROTOCOL.read_bytes())
    revision = audit_checkout(source, protocol)
    fit = json.loads((ARTIFACTS / "fit-freeze.json").read_bytes())
    model_hashes = {file: sha(ARTIFACTS / file) for file in ("full.json", "no_nli.json")}
    if model_hashes != fit["artifacts_sha256"]:
        raise ValueError("Controller artifacts differ from the fit freeze")
    if (fit["source"]["collection"]["minilm"] != MINILM_REVISION
            or fit["source"]["collection"]["nli"] != NLI_REVISION):
        raise ValueError("Controller feature model revisions differ from runtime")
    tags = {item["name"]: item["digest"] for item in local_json("/api/tags")["models"]}
    if tags.get(QWEN) != QWEN_DIGEST or checksum(
            [DIRECT_V2_PROMPT, RESPONSE_SCHEMAS["verify-direct-v2"]]) != PROMPT_SCHEMA:
        raise ValueError("Local Qwen digest or verifier prompt/schema changed")
    dev = protocol["development"]
    settings = protocol["settings"]
    freeze = {
        "revision": revision, "protocol_sha256": sha(PROTOCOL), "smoke": smoke,
        "extraction_validation_sha256": sha(extraction_validation) if validated else None,
        "controller_sha256": model_hashes, "fit_freeze_sha256": sha(ARTIFACTS / "fit-freeze.json"),
        "qwen": QWEN_DIGEST, "qwen_name": QWEN, "ollama": local_json("/api/version")["version"],
        "minilm": MINILM_REVISION, "nli": NLI_REVISION, "verifier_prompt_schema": PROMPT_SCHEMA,
        "settings": settings, "provider_settings": SETTINGS, "torch": torch.__version__,
        "transformers": transformers.__version__, "python": platform.python_version(),
        "runner_code": {str(path.relative_to(ROOT)): sha(path) for path in (
            Path(__file__).resolve(), ROOT / "trace_mem/memora_benchmark.py",
            ROOT / "trace_mem/llm_tasks.py", ROOT / "trace_mem/baselines.py",
            ROOT / "trace_mem/context_extraction.py",
            ROOT / "trace_mem/providers.py", ROOT / "trace_mem/features_v3.py",
            ROOT / "trace_mem/memory.py", ROOT / "trace_mem/claims.py",
        )},
    }
    output.mkdir(parents=True, exist_ok=True)
    freeze_path = output / "freeze.json"
    if freeze_path.exists() and json.loads(freeze_path.read_bytes()) != freeze:
        raise ValueError("Use a new output directory for a changed run freeze")
    write(freeze_path, freeze)

    history = source / dev["path"]
    chosen = questions(history / f"evaluation_questions_{history.name}.json", dev["selectors"])
    all_events = tuple(replay(history, through=max(q.observed_on for q in chosen)))
    events = all_events
    if smoke:
        # Limit observations before extraction and leave query membership fixed.
        ids = list(dict.fromkeys(event.session_id for event in all_events))[:dev["smoke_session_limit"]]
        events = tuple(event for event in all_events if event.session_id in ids)

    started = time.perf_counter()
    torch.set_num_threads(4)
    embed = CachedMiniLM()
    builders = {"T1": V3Features(embed, pinned_nli(nli)), "T1-no-NLI": V3Features(embed)}
    models = {"T1": load_model(ARTIFACTS / "full.json"),
              "T1-no-NLI": load_model(ARTIFACTS / "no_nli.json")}
    request_cap = settings["smoke_max_requests" if smoke else "max_requests"]
    provider = ChatProvider(ProviderConfig("ollama", QWEN, request_cap, **SETTINGS),
                            output / "responses.sqlite")
    tasks = LLMTasks(provider, verification_mode=MODE)
    before = provider.stats()
    collect = contextual_prepare if validated else prepare
    prepared, errors = collect(events, tasks)
    report = {"smoke": smoke, "questions": len(chosen), "events": len(events),
              "user_events": sum(event.role == "user" for event in events),
              "full_development_user_events": sum(event.role == "user" for event in all_events),
              "claims": len(prepared), "extraction_failures": errors, "modes": {},
              "claim_intents": dict(Counter(item.claim.intent for item in prepared)),
              "distinct_predicates": len({item.claim.predicate for item in prepared}),
              "explicit_date_claims": sum(item.claim.explicit_effective_date for item in prepared),
              "claim_bearing_turns": len({item.source.reference for item in prepared}),
              "before": before}
    predictions = []
    for question in chosen:
        cutoff_events = tuple(event for event in events if event.observed_on <= question.observed_on)
        cutoff_claims = tuple(item for item in prepared if item.source.observed_on <= question.observed_on)
        for mode in ("fixed", "closed-loop"):
            states = run_suite(cutoff_events, cutoff_claims, tasks, entity=history.name, models=models,
                               builders=builders, mode=mode, cap=settings["cap"], seed=settings["seed"],
                               random_probability=settings["random_probability"])
            outcomes = answer_suite(question, states, tasks, entity=history.name,
                                    k=settings["k"], embed=embed)
            for method, record in outcomes.items():
                predictions.append({"question_id": question.identifier, "task": question.task,
                                    "mode": mode, "method": method, **record})
                aggregate = report["modes"].setdefault(mode, {}).setdefault(method, Counter())
                for key in ("verification_attempts", "verification_failures", "stale_targets",
                            "eligible_candidates", "retrieved"):
                    aggregate[key] += record[key]
                aggregate["answered"] += record["answer"] is not None
                aggregate["reader_errors"] += record["reader_error"]
                aggregate.update({f"transition_{key}": count
                                  for key, count in record["transitions"].items()})
    report["after"] = provider.stats()
    report["wall_seconds"] = time.perf_counter() - started
    report["ollama_resident"] = [
        {key: item.get(key) for key in ("size", "size_vram", "context_length")}
        for item in local_json("/api/ps")["models"] if item["digest"] == QWEN_DIGEST
    ]
    write(output / "predictions.json", predictions)
    write(output / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--nli", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--extraction-validation", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.source, args.nli, args.output, smoke=args.smoke,
                         extraction_validation=args.extraction_validation), sort_keys=True))
