"""Run the frozen fictional extractor and reader comparison, with per-case checkpoints."""

from argparse import ArgumentParser
from collections import Counter
from datetime import date
import json
from pathlib import Path
import re
import time

from scripts.compare_local_verifiers import QWEN, SETTINGS, local_json
from scripts.run_memora import ROOT, sha, write
from scripts.step33_fixtures import extraction, reader
from scripts.updateset_v2_pilot import QWEN_DIGEST
from trace_mem.data.memora import Event
from trace_mem.extractor_v3 import eligible_user_fields, extract
from trace_mem.llm_tasks import LLMTasks
from trace_mem.memory import Fact, Source
from trace_mem.providers import ChatProvider, LimitExceeded, ProviderConfig, ProviderError
from trace_mem.reader_v2 import read as original_reader
from trace_mem.reader_v3 import read as candidate_reader


SPEC = ROOT / "docs/step33_freeze.json"
TODAY = date(2026, 3, 1)


def match(predictions, expected):
    remaining = [(value.casefold(), intent) for value, intent in expected]
    hit = 0
    for value, intent in predictions:
        for i, (want, action) in enumerate(remaining):
            if intent == action and re.search(r"(?<!\w)" + re.escape(want) + r"(?!\w)", value.casefold()):
                hit += 1
                remaining.pop(i)
                break
    return hit


def extraction_row(row, arm, provider):
    event = Event(TODAY, 1, 1, row["role"], row["message"])
    recovered = assistant_leaks = 0
    failed = False
    quarantined = False
    try:
        if arm == "original":
            findings = LLMTasks(provider).extract(event)
        else:
            result = extract(provider, event)
            findings = result.findings
            failed, recovered, quarantined = bool(result.failed), result.recovered, result.quarantine
            assistant_leaks = event.role == "assistant" and bool(eligible_user_fields(result))
    except (LimitExceeded, ProviderError) as error:
        if isinstance(error, LimitExceeded) and "preflight" not in str(error):
            raise
        findings, failed = (), True
    pairs = [(f.value, f.intent) for f in findings]
    support = (sum(f.value.casefold() in row["message"].casefold() for f in findings) if arm == "original"
               else sum(f.value in row["message"][f.start:f.end] and f.source == "1/1"
                        and f.speaker == row["role"] for f in findings))
    hit = match(pairs, row["expected"])
    return {"expected": len(row["expected"]), "predicted": len(pairs), "correct": hit,
            "supported": support, "failed": int(failed), "recovered": recovered,
            "assistant_leaks": int(assistant_leaks),
            "deletion_exact": int(row["id"].startswith("delete") and hit == 1),
            "quarantined": quarantined, "distinct": int(row["id"].startswith("repeat") and hit == 2)}


def reader_row(row, arm, provider):
    facts = tuple(Fact(str(i), "fictional", "evidence", v, Source(TODAY, f"source/{i}"), TODAY)
                  for i, v in enumerate(row["facts"]))
    fn = original_reader if arm == "original" else candidate_reader
    try:
        answer = fn(provider, row["question"], facts, as_of=TODAY, mode="reasoning").answer
    except (LimitExceeded, ProviderError) as error:
        if isinstance(error, LimitExceeded) and "preflight" not in str(error):
            raise
        return "invalid"
    if set(answer.citations) == {str(i) for i in row["expected"]}:
        return "correct"
    return "abstained-incorrect" if not answer.citations else "wrong-evidence"


def summarize(rows, gates):
    arms = {}
    for arm in ("original", "candidate"):
        e = Counter()
        r = Counter()
        for item in rows:
            if item["type"] == "extraction":
                e.update({k: int(v) for k, v in item[arm].items()})
            else:
                r[item[arm]] += 1
                r["correct_abstentions"] += item["id"].startswith(("insufficient", "conflict")) and item[arm] == "correct"
        precision = e["correct"] / e["predicted"] if e["predicted"] else 0
        recall = e["correct"] / e["expected"]
        arms[arm] = {"extraction": dict(e, precision=precision, recall=recall,
                                          f1=2*precision*recall/(precision+recall) if precision+recall else 0),
                     "reader": dict(r, accuracy=r["correct"] / (r.total() - r["correct_abstentions"]))}
    e, r = arms["candidate"].values()
    eg, rg = gates["extraction_gate"], gates["reader_gate"]
    detector = all(item["candidate"]["quarantined"] for item in rows if item["id"].startswith("delete"))
    extraction_gate = {
        "precision": e["precision"] >= eg["minimum_precision"],
        "recall": e["recall"] >= eg["minimum_recall"],
        "recall_gain": e["recall"] - arms["original"]["extraction"]["recall"] >= eg["minimum_recall_gain"],
        "distinct_events": e["distinct"] >= eg["minimum_distinct_event_pairs"],
        "failures": e["failed"] <= eg["maximum_failed_cases"],
        "deletions": e["deletion_exact"] == eg["deletions_required"] and detector,
        "assistant_trust": e["assistant_leaks"] <= eg["assistant_trust_violations"],
    }
    reader_gate = {
        "accuracy": r["accuracy"] >= rg["minimum_accuracy"],
        "gain": r["accuracy"] - arms["original"]["reader"]["accuracy"] >= rg["minimum_accuracy_gain"],
        "invalid": r.get("invalid", 0) <= rg["maximum_invalid"],
        "abstention": r["correct_abstentions"] >= rg["minimum_abstentions_correct"],
    }
    return {"arms": arms, "extraction_gate": extraction_gate, "reader_gate": reader_gate,
            "external_permitted": all(extraction_gate.values()) and all(reader_gate.values())}


def run(root):
    if (ROOT / "results").resolve() not in root.resolve().parents:
        raise ValueError("Use ignored local output")
    if {r["name"]: r["digest"] for r in local_json("/api/tags")["models"]}.get(QWEN) != QWEN_DIGEST:
        raise ValueError("Pinned Qwen unavailable")
    config = json.loads(SPEC.read_bytes())
    files = (SPEC, Path(__file__), ROOT / "scripts/step33_fixtures.py",
             ROOT / "trace_mem/extractor_v3.py", ROOT / "trace_mem/reader_v3.py")
    manifest = {p.name: sha(p) for p in files} | {"qwen": QWEN_DIGEST, "settings": SETTINGS}
    root.mkdir(parents=True, exist_ok=True)
    lock = root / "freeze.json"
    if lock.exists() and json.loads(lock.read_bytes()) != manifest:
        raise ValueError("Changed validation implementation or protocol")
    write(lock, manifest)
    checkpoint = root / "rows.json"
    rows = json.loads(checkpoint.read_bytes()) if checkpoint.exists() else []
    providers = {}
    for kind, arm in (("extraction", "original"), ("extraction", "candidate"),
                      ("reader", "original"), ("reader", "candidate")):
        settings = SETTINGS | {"max_output_tokens": 384 if kind == "reader" else 256}
        providers[kind, arm] = ChatProvider(ProviderConfig("ollama", QWEN,
            config["fixture_request_cap"], **settings), root / f"{kind}-{arm}.sqlite")
    cases = [("extraction", row) for row in extraction()] + [("reader", row) for row in reader()]
    start = time.perf_counter()
    for kind, row in cases[len(rows):]:
        fn = extraction_row if kind == "extraction" else reader_row
        outcomes = {arm: fn(row, arm, providers[kind, arm]) for arm in ("original", "candidate")}
        rows.append(outcomes | {"type": kind, "id": row["id"]})
        write(checkpoint, rows)
        if len(rows) % 10 == 0:
            print(len(rows), "/", len(cases), flush=True)
    summary = summarize(rows, config)
    summary["usage"] = {f"{k}-{a}": p.stats() for (k, a), p in providers.items()}
    summary["wall_seconds"] = time.perf_counter() - start
    summary["manifest"] = manifest
    summary["rows"] = rows
    write(root / "report.json", summary)
    return {k: v for k, v in summary.items() if k != "rows"}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    print(json.dumps(run(parser.parse_args().output)))
