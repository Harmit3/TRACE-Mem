"""Audit a paired TRACE-UpdateSet release and emit safe aggregate counts."""

import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from statistics import mean, median

from trace_mem.data.updateset import read_release
from trace_mem.training import _inputs, eligible_case


def summarize(source: Path, paired: Path, ledger: Path, packet: Path) -> dict:
    before, initial = read_release(source)
    after, final = read_release(paired)
    source_hash = initial["files"]["cases.jsonl"]
    if (initial["settings"] != final["settings"]
            or (final["lineage"] or {}).get("parent_cases_sha256") != source_hash
            or len(before) != len(after)):
        raise ValueError("Paired release does not derive from the source release")
    summary = {split: Counter(eligible=0, pairs=0, positive=0, negative=0, pending_gold=0)
               for split in ("train", "validation", "test")}
    decisions = {split: Counter() for split in ("train", "validation")}
    for prior, current in zip(before, after):
        split = prior["split"]
        eligible = split != "test" and eligible_case(_inputs(prior))
        if not eligible:
            if prior != current:
                raise ValueError("Test or ineligible case changed")
            continue
        stable = set(prior) - {"outcomes", "verification_helpful"}
        if any(prior[key] != current[key] for key in stable):
            raise ValueError("Original case or gold changed")
        outcome = current["outcomes"]
        if (not outcome or outcome["origin"] != "recorded_verifier"
                or (prior["outcomes"] is not None and outcome != prior["outcomes"])):
            raise ValueError("Expected a preserved or newly recorded outcome")
        summary[split]["eligible"] += 1
        summary[split]["pairs"] += 1
        label = current["verification_helpful"]
        summary[split]["pending_gold" if label is None else "positive" if label else "negative"] += 1
        decisions[split][f'{outcome["unverified"]["operation"]}->{outcome["verified"]["operation"]}'] += 1

    with closing(sqlite3.connect(ledger.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        attempts = db.execute(
            "SELECT status, input_tokens, output_tokens, latency_ms, cost, model FROM attempt"
        ).fetchall()
        cache_hits, = db.execute("SELECT COUNT(*) FROM cache_hit").fetchone()
    successful = [item for item in attempts if item[0] == "ok"]
    times = sorted(item[3] for item in successful)
    timing = ({key: round(value, 3) for key, value in {
        "sum": sum(times), "mean": mean(times), "median": median(times),
        "p95": times[math.ceil(len(times) * 0.95) - 1], "max": max(times),
    }.items()} if times else {})
    return {
        "source_cases_sha256": source_hash, "paired_cases_sha256": final["files"]["cases.jsonl"],
        "review_packet_sha256": hashlib.sha256(packet.read_bytes()).hexdigest(),
        "split_counts": {split: dict(counts) for split, counts in summary.items()},
        "decision_transitions": {split: dict(counts) for split, counts in decisions.items()},
        "training_ready": all(summary[split]["positive"] and summary[split]["negative"]
                              for split in ("train", "validation")),
        "attempts": len(attempts), "failures": len(attempts) - len(successful),
        "statuses": dict(Counter(item[0] for item in attempts)),
        "input_tokens": sum(item[1] or 0 for item in attempts),
        "output_tokens": sum(item[2] or 0 for item in attempts),
        "cost_nanodollars": sum(item[4] for item in attempts),
        "models": sorted({item[5] for item in attempts if item[5]}),
        "success_latency_ms": timing, "cache_hits": cache_hits,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "paired", "ledger", "packet"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.source, args.paired, args.ledger, args.packet),
                     indent=2, sort_keys=True))
