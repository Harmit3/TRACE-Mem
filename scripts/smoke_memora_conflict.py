"""Exercise actual conflict and deletion paths with a frozen fictional transcript."""

import argparse
from datetime import date
import json
from pathlib import Path
import time

from scripts.compare_local_verifiers import MODE, QWEN, SETTINGS, local_json
from scripts.run_memora import ARTIFACTS, ROOT, sha, write
from scripts.updateset_v2_pilot import QWEN_DIGEST
from trace_mem.data.memora import Event
from trace_mem.features_v3 import CachedMiniLM, V3Features, pinned_nli
from trace_mem.llm_tasks import LLMTasks
from trace_mem.memora_benchmark import Question, answer_suite, prepare, run_suite
from trace_mem.providers import ChatProvider, ProviderConfig
from trace_mem.training import load_model


TRANSCRIPT = (
    "Please remember that I work at Lark Office.",
    "I switched employers to Reed Office. I now work at Reed Office permanently.",
    "Forget that I worked at Lark Office. Remove Lark Office from memory.",
)
QUERY = Question("synthetic-job", "diagnostic", "Where do I work now?", date(2025, 1, 3))


def exercise(nli, output):
    import torch

    if (ROOT / "results").resolve() not in output.resolve().parents:
        raise ValueError("Keep diagnostic responses under ignored results/")
    tags = {item["name"]: item["digest"] for item in local_json("/api/tags")["models"]}
    if tags.get(QWEN) != QWEN_DIGEST:
        raise ValueError("Local Qwen does not match the pinned digest")
    frozen = json.loads((ARTIFACTS / "fit-freeze.json").read_bytes())
    if any(sha(ARTIFACTS / path) != digest for path, digest in frozen["artifacts_sha256"].items()):
        raise ValueError("Controller artifact hash mismatch")
    output.mkdir(parents=True, exist_ok=False)
    events = tuple(Event(date(2025, 1, i), i, 1, "user", message)
                   for i, message in enumerate(TRANSCRIPT, 1))
    started = time.perf_counter()
    torch.set_num_threads(4)
    mini = CachedMiniLM()
    calls = 0
    nli_model = pinned_nli(nli)

    def track_nli(premise, hypothesis):
        nonlocal calls
        calls += 1
        return nli_model(premise, hypothesis)

    builders = {"T1": V3Features(mini, track_nli), "T1-no-NLI": V3Features(mini)}
    models = {"T1": load_model(ARTIFACTS / "full.json"),
              "T1-no-NLI": load_model(ARTIFACTS / "no_nli.json")}
    provider = ChatProvider(ProviderConfig("ollama", QWEN, 100, **SETTINGS),
                            output / "responses.sqlite")
    tasks = LLMTasks(provider, verification_mode=MODE)
    prepared, errors = prepare(events, tasks)
    report = {"claims": len(prepared), "extraction_failures": errors, "modes": {}}
    for mode in ("fixed", "closed-loop"):
        states = run_suite(events, prepared, tasks, entity="synthetic", models=models,
                           builders=builders, mode=mode, cap=2, seed=23)
        answers = answer_suite(QUERY, states, tasks, entity="synthetic", k=8, embed=mini)
        report["modes"][mode] = {}
        for method, row in answers.items():
            memory, _ = states[method]
            report["modes"][mode][method] = {
                "verification_attempts": row["verification_attempts"],
                "verification_failures": row["verification_failures"],
                "eligible_candidates": row["eligible_candidates"],
                "reader_error": row["reader_error"],
                "mentions_expected_job": "reed office" in (row["answer"] or "").casefold(),
                "forgotten_value_retrievable": any(f.value.casefold() == "lark office"
                    for f in memory.retrieve("synthetic", None, as_of=date(2025, 1, 1))),
                "deletions": row["transitions"].get("delete", 0),
            }
    report.update(nli_calls=calls, provider=provider.stats(), wall_seconds=time.perf_counter() - started)
    write(output / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nli", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(exercise(args.nli, args.output), sort_keys=True))
