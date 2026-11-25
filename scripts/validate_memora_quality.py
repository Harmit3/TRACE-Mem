"""Compare frozen local extractors and independently specified rubric judgments."""

from argparse import ArgumentParser
from collections import Counter
from datetime import date
import json
from pathlib import Path
import time

from scripts.compare_local_verifiers import QWEN, SETTINGS, local_json
from scripts.run_memora import ROOT, sha, write
from scripts.updateset_v2_pilot import QWEN_DIGEST
from trace_mem.context_extraction import extract_event
from trace_mem.data.memora import Event
from trace_mem.llm_tasks import LLMTasks
from trace_mem.local_rubric import judge
from trace_mem.providers import ChatProvider, ProviderConfig, ProviderError


PROTOCOL = ROOT / "docs/memora_step20_validation.json"


def key(predicate, value, intent):
    return predicate.casefold(), " ".join(value.casefold().split()), intent


def metrics(rows):
    correct = sum(len(found & gold) for found, gold in rows)
    produced = sum(len(found) for found, _ in rows)
    expected = sum(len(gold) for _, gold in rows)
    delete = lambda values: {value for value in values if value[-1] == "delete"}
    deletion_true = sum(len(delete(found & gold)) for found, gold in rows)
    deletion_expected = sum(len(delete(gold)) for _, gold in rows)
    deletion_found = sum(len(delete(found)) for found, _ in rows)
    return {"exact_matches": correct, "produced": produced, "expected": expected,
            "precision": correct / produced if produced else 0,
            "recall": correct / expected if expected else 0,
            "f1": 2 * correct / (produced + expected) if produced + expected else 0,
            "unmatched_predictions": produced - correct, "missed": expected - correct,
            "matched_deletions": deletion_true, "expected_deletions": deletion_expected,
            "predicted_deletions": deletion_found,
            "delete_recall": deletion_true / deletion_expected if deletion_expected else 0}


def provider(output):
    tags = {row["name"]: row["digest"] for row in local_json("/api/tags")["models"]}
    if tags.get(QWEN) != QWEN_DIGEST:
        raise ValueError("Pinned local Qwen model unavailable")
    return ChatProvider(ProviderConfig("ollama", QWEN, 180, **SETTINGS), output)


def validate(output):
    if (ROOT / "results").resolve() not in output.resolve().parents:
        raise ValueError("Keep raw validation output under ignored results/")
    design = json.loads(PROTOCOL.read_bytes())
    output.mkdir(parents=True, exist_ok=False)
    backend = provider(output / "responses.sqlite")
    tasks = LLMTasks(backend)
    results = {}
    started = time.perf_counter()
    for improved in (False, True):
        rows, details = [], {}
        failures = 0
        before = backend.stats()
        for i, (name, prior, text, gold) in enumerate(design["cases"], 1):
            event = Event(date(2025, 2, 2), i, len(prior) + 1, "user", text)
            try:
                found = {key(c.predicate, c.value, c.intent)
                         for c in extract_event(tasks, event, prior, improved=improved)}
            except ProviderError:
                failures += 1
                found = set()
            expected = {key(*item) for item in gold}
            rows.append((found, expected))
            details[name] = sorted(found)
        after = backend.stats()
        results["contextual" if improved else "original"] = {
            **metrics(rows), "failures": failures, "details": details,
            "usage": {k: after[k] - before[k] for k in (
                "attempts", "cache_hits", "input_tokens", "output_tokens", "latency_ms")}}
    counts = Counter()
    for answer, check, expected in design["judge"]:
        try:
            observed = judge(backend, answer, check)
        except ProviderError:
            observed = "error"
        counts[f"{expected}->{observed}"] += 1
    accuracy = (counts["yes->yes"] + counts["no->no"]) / len(design["judge"])
    gate = design["gate"]
    a, b = results["original"], results["contextual"]
    report = {"protocol_sha256": sha(PROTOCOL), "qwen_digest": QWEN_DIGEST, "extractors": results,
              "judge": {"accuracy": accuracy, "counts": dict(counts),
                        "passes": accuracy >= gate["judge_min_accuracy"]},
              "extractor_passes": (b["precision"] >= gate["min_precision"]
                  and b["recall"] >= gate["min_recall"] and b["delete_recall"] >= gate["min_delete_recall"]
                  and b["f1"] - a["f1"] >= gate["min_f1_gain"]),
              "provider": backend.stats(), "wall_seconds": time.perf_counter() - started}
    write(output / "report.json", report)
    return report


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = validate(args.output)
    for row in result["extractors"].values():
        row.pop("details")
    print(json.dumps(result, sort_keys=True))
