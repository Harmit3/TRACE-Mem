"""Run the frozen Step 31 robustness grid over the Step 30 synthetic cohort."""

from argparse import ArgumentParser
from collections import Counter, defaultdict
from dataclasses import replace
from functools import lru_cache
import json
from pathlib import Path
import time

from scripts.run_step30 import (
    ARTIFACTS, DESIGN, ENTITY, MINILM_REVISION, MODE, NLI_REVISION, QWEN, QWEN_DIGEST,
    ROOT, SETTINGS, CachedMiniLM, V3Features, cap_for, dataset_hash, generate, load_model,
    local_json, make_adaptive, memory_metrics, pinned_nli, project, sha, write,
)
from scripts.run_t2_development import frozen_rows
from scripts.step31_cache import MeasuredCache
from scripts.summarize_step30 import summarize
from trace_mem.adaptive_verification import AdaptiveAllocation, neutralized_score
from trace_mem.evidence_index_v2 import EvidenceIndexV2
from trace_mem.llm_tasks import LLMTasks, DIRECT_V2_PROMPT, RESPONSE_SCHEMAS
from scripts.compare_local_verifiers import checksum
from scripts.updateset_v2_pilot import PROMPT_SCHEMA
from trace_mem.memora_benchmark import Question, run_suite
from trace_mem.providers import LimitExceeded, ProviderConfig, ProviderError
from trace_mem.reader_v2 import BUDGETS, read
from trace_mem.retrieval_diagnostic import trim


PROTOCOL = ROOT / "docs/step31_freeze.json"


def reproduce(previous, expected_hash):
    report = previous / "report.json"
    if sha(report) != expected_hash:
        raise ValueError("Step 30 report hash does not match")
    data = json.loads(report.read_bytes())
    for row, file in zip(data["histories"], sorted((previous / "histories").glob("*.json")), strict=True):
        if row != json.loads(file.read_bytes()):
            raise ValueError("Step 30 checkpoint mismatch")
    result = summarize(data, json.loads(DESIGN.read_bytes()))
    if result != json.loads((ROOT / "docs/step30_artifacts/aggregate.json").read_bytes()):
        raise ValueError("Step 30 aggregate mismatch")
    return data, [r for r in result["contrasts"] if r["budget"] == 50
                  and r["left"] == "T2" and r["right"] == "H-paced"]


def answer_score(text, values, expected):
    if text is None:
        return "abstained"
    if len(values) > 1:
        return "contradictory"
    return "correct" if values == {expected} else "incorrect"


def reader(memory, history, embed, backends):
    day = history["final"]
    idx = EvidenceIndexV2(project(memory, history, day), "frozen-public-synthetic")
    result = {}
    for mode, text in (
        ("short", f"What is the current {history['predicate']}?"),
        ("reasoning", "What was the total spending in these records?"),
    ):
        question = Question("synthetic", mode, text, day)
        handle = idx.retrieve(text, day, embed, k=8)
        facts = trim(question, idx.materialize(handle, ENTITY), 3000, 8)
        if any(history["private"] in f.value for f in facts):
            raise ValueError("Restricted evidence in reader context")
        try:
            answer = read(backends[mode], text, facts, as_of=day, mode=mode).answer
        except LimitExceeded:
            raise
        except ProviderError:
            if backends[mode].fatal:
                raise backends[mode].fatal
            result[mode] = "invalid"
            continue
        cited = {f.value for f in facts if f.fact_id in answer.citations
                 and f.predicate == history["predicate"]}
        if mode == "short":
            result[mode] = answer_score(answer.text, cited, history["current"])
        else:
            result[mode] = ("abstained" if answer.text is None else
                            "correct" if f"${history['cost']}.00" in answer.text else "incorrect")
    return result


def evaluate(history, index, design, models, builders, adaptive, verifier, readers, embed, old):
    rows = []
    comparisons = {(r["mode"], r["budget"], r["method"]): r for r in old["rows"]
                   if r["seed"] == design["seed"]}
    tasks = LLMTasks(verifier, verification_mode=MODE)
    traces = []
    for budget in design["budgets"]:
        cap = cap_for(budget, index)
        for mode, horizon, methods in (
            ("fixed", None, design["baselines"] + design["adaptive"]),
            ("closed-loop", None, design["baselines"]),
            *(("closed-loop", h, design["adaptive"]) for h in design["horizon_percent"]),
        ):
            counts = defaultdict(Counter)
            events = defaultdict(list)

            def observe(method, item, live, target, remaining, verdict, applied, failed, memory):
                if item.fact_id not in history["decisions"]:
                    return
                spec = history["decisions"][item.fact_id]
                spent = verdict is not None
                after = sorted(f.value for f in memory.retrieve(
                    ENTITY, history["predicate"], as_of=spec["day"]))
                metrics = counts[method]
                metrics["live_eligible"] += live is not None
                metrics["logical_input_tokens"] += (verifier.current_usage or (0, 0))[0] if spent else 0
                metrics["logical_output_tokens"] += (verifier.current_usage or (0, 0))[1] if spent else 0
                metrics["unmetered_calls"] += spent and verifier.current_usage is None
                if applied and not failed:
                    without = item.claim.value if item.claim.intent == "correct" else target.value
                    metrics["helpful"] += without != spec["expected"] and after == [spec["expected"]]
                    metrics["harmful"] += without == spec["expected"] and after != [spec["expected"]]
                if spent:
                    metrics["positions_total"] += len(events[method]) + 1
                events[method].append({
                    "kind": spec["kind"], "day": spec["day"].isoformat(), "proposal": spec["proposal"],
                    "expected": spec["expected"], "live": live.value if live is not None else None,
                    "target": target.value if target is not None else None, "remaining": remaining,
                    "verdict": verdict, "applied": applied, "after": after,
                })

            adapted = adaptive[horizon or 100]
            outcomes = run_suite(history["events"], history["claims"], tasks, entity=ENTITY,
                                 models=models, builders=builders, mode=mode, cap=cap,
                                 seed=design["seed"], adaptive=adapted, methods=methods,
                                 decision_observer=observe)
            if verifier.fatal:
                raise verifier.fatal
            for method, (memory, stats) in outcomes.items():
                measured = memory_metrics(memory, history)
                if measured["deletion"] != 2 or measured["authorized_deletion"] != 2:
                    raise ValueError("Policy failed authorization or deletion gate")
                data = dict(stats, **measured)
                if horizon in (100, None) and method != "T2-no-NLI":
                    expected = comparisons[mode, budget, method]
                    if any(expected[k] != value for k, value in data.items()):
                        raise ValueError(f"Step 30 replay diverged: {history['id']} {mode} {budget} {method}")
                metrics = counts[method]
                data.update({k: metrics[k] for k in (
                    "live_eligible", "logical_input_tokens", "logical_output_tokens",
                    "unmetered_calls", "positions_total", "helpful", "harmful")})
                if not 0 <= data["verification_attempts"] <= cap or data["unmetered_calls"]:
                    raise ValueError("Unmetered verifier call or cap violation")
                data.update(method=method, mode=mode, budget=budget, horizon=horizon)
                sample = design["reader"]
                if (mode == sample["mode"] and budget == sample["budget"]
                        and horizon in (None, sample["horizon"]) and history["member"] in sample["members"]):
                    data["qa"] = reader(memory, history, embed, readers)
                rows.append(data)
                if budget == 50 and horizon in (None, 100) and method in {"T2", "B3"}:
                    traces.append(dict(method=method, mode=mode, turns=events[method]))
    return dict(history=history["id"], family=history["family"], rows=rows, traces=traces)


def run(previous, outcomes, nli, output):
    import torch

    if (ROOT / "results").resolve() not in output.resolve().parents or output.resolve() == previous.resolve():
        raise ValueError("Use a separate ignored results directory")
    design = json.loads(PROTOCOL.read_bytes())
    old, primary = reproduce(previous, design["step30_report_sha256"])
    source_design = json.loads(DESIGN.read_bytes())
    histories = list(generate(source_design))
    if dataset_hash(histories) != source_design["dataset_sha256"]:
        raise ValueError("Step 30 dataset hash changed")
    models_found = {row["name"]: row["digest"] for row in local_json("/api/tags")["models"]}
    if models_found.get(QWEN) != QWEN_DIGEST or checksum(
            [DIRECT_V2_PROMPT, RESPONSE_SCHEMAS["verify-direct-v2"]]) != PROMPT_SCHEMA:
        raise ValueError("Verifier digest or prompt/schema changed")
    artifacts = json.loads((ARTIFACTS / "fit-freeze.json").read_bytes())["artifacts_sha256"]
    if any(sha(ARTIFACTS / name) != value for name, value in artifacts.items()):
        raise ValueError("Frozen controller artifacts changed")
    manifest = {"design": sha(PROTOCOL), "dataset": dataset_hash(histories), "artifacts": artifacts,
                "qwen": QWEN_DIGEST, "minilm": MINILM_REVISION, "nli": NLI_REVISION,
                "settings": SETTINGS, "training_features": sha(outcomes),
                "runner": sha(Path(__file__)),
                "cache_code": sha(Path(__file__).with_name("step31_cache.py")),
                "legacy_caches": {name: sha(previous / f"{name}.sqlite")
                                  for name in ("verifier", "reader-short", "reader-reasoning")}}
    directory = output / "histories"
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "freeze.json"
    if manifest_path.exists() and json.loads(manifest_path.read_bytes()) != manifest:
        raise ValueError("Run inputs changed")
    write(manifest_path, manifest)
    started = time.perf_counter()
    torch.set_num_threads(4)
    encoder = CachedMiniLM()
    vectors = {}

    def embed(values):
        missing = list(dict.fromkeys(v for v in values if v not in vectors))
        if missing:
            vectors.update(zip(missing, encoder(missing), strict=True))
        return [vectors[v] for v in values]

    full = V3Features(embed, lru_cache(maxsize=4096)(pinned_nli(nli)))
    without = V3Features(embed)
    models = {method: load_model(ARTIFACTS / file) for method, file in (
        ("T1", "full.json"), ("T1-no-NLI", "no_nli.json"))}
    builders = {"T1": full, "T1-no-NLI": without, "T2": full, "T2-no-NLI": without, "H-paced": without}
    train = frozen_rows(outcomes)["train"]

    def no_nli(vector):
        return neutralized_score(models["T1-no-NLI"], (vector[0], 0.0, *vector[2:]))

    reduced_reference = tuple(sorted(map(no_nli, train)))
    adaptive = {}
    for horizon in design["horizon_percent"]:
        candidates = horizon * source_design["nominal_opportunities"] // 100
        adaptive[horizon] = make_adaptive(candidates, train, models["T1"])
        adaptive[horizon]["T2-no-NLI"] = AdaptiveAllocation(no_nli, reduced_reference, candidates)

    verifier = MeasuredCache(ProviderConfig("ollama", QWEN, design["max_new_verifier_requests"],
                             **SETTINGS), output, "verifier", previous / "verifier.sqlite", tokens=True)
    readers = {mode: MeasuredCache(ProviderConfig("ollama", QWEN, design["max_new_reader_requests"],
                                   **(SETTINGS | {"max_output_tokens": BUDGETS[mode]})), output,
                                  f"reader-{mode}", previous / f"reader-{mode}.sqlite")
               for mode in design["reader"]["questions"]}
    result = []
    for i, (history, prior) in enumerate(zip(histories, old["histories"], strict=True)):
        path = directory / f"{i:03d}.json"
        if path.exists():
            row = json.loads(path.read_bytes())
        else:
            row = evaluate(history, i, design, models, builders, adaptive, verifier, readers, embed, prior)
            write(path, row)
        result.append(row)
        if (i + 1) % 5 == 0:
            print(json.dumps({"completed": i + 1, "new_verifier": verifier.provider.stats()["attempts"],
                              "new_reader": readers["short"].provider.stats()["attempts"]}), flush=True)
    report = {"reproduced": primary, "histories": result, "manifest": manifest,
              "verifier": verifier.provider.stats(), "reader": {k: v.provider.stats() for k, v in readers.items()},
              "prior_verifier_uses": sum(r["verification_attempts"] for h in result for r in h["rows"]),
              "wall_seconds": time.perf_counter() - started}
    write(output / "report.json", report)
    return report


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    for arg in ("previous", "outcomes", "nli", "output"):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    result = run(args.previous, args.outcomes, args.nli, args.output)
    print(json.dumps({k: v for k, v in result.items() if k != "histories"}))
