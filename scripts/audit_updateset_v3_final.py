"""Audit the frozen release and prepare an identical-row no-NLI projection."""

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sqlite3
from contextlib import closing

from scripts.collect_updateset_v3_final import audit, encode, save
from trace_mem.controller import FEATURE_NAMES
from trace_mem.data.updateset_v2 import sha
from trace_mem.data.updateset_v3 import cases as pilot_cases
from trace_mem.data.updateset_v3_final import generate


def review_release(dataset: Path, release: Path, ablation: Path | None = None) -> dict:
    source = json.loads((dataset / "manifest.json").read_bytes())
    expected = generate()
    manifest = json.loads((release / "freeze.json").read_bytes())
    report = json.loads((release / "report.json").read_bytes())
    data = (release / "outcomes.jsonl").read_bytes()
    if (manifest["dataset"] != source or sha(data) != report["outcomes_sha256"]
            or tuple(manifest["features"]) != FEATURE_NAMES or any(
                sha((dataset / path).read_bytes()) != checksum
                for path, checksum in source["files"].items()
            ) or b"".join(map(encode, expected)) != (dataset / "histories.jsonl").read_bytes()):
        raise ValueError("Release hashes, source or feature order disagree")
    rows = [json.loads(line) for line in data.splitlines()]
    if len(rows) != len(expected) or audit(rows) != report["groups"]:
        raise ValueError("Outcome distribution does not reproduce")

    families = {}
    utterances = {}
    seen = set()
    pilot = {" ".join(turn["text"].casefold().split()) for case in pilot_cases()
             for turn in case["transcript"]}
    projected = []
    abstained_rows = Counter()
    for history, result in zip(expected, rows):
        if any(history[key] != result[key] for key in ("id", "split", "family", "cap")):
            raise ValueError("History row differs from frozen ordering")
        split = history["split"]
        if families.setdefault(history["family"], split) != split:
            raise ValueError("Family appears in multiple partitions")
        calls = 0
        failures = 0
        if len(result["steps"]) != len(history["turns"]):
            raise ValueError("Unrecorded history turn")
        for number, (original, step) in enumerate(zip(history["turns"], result["steps"]), 1):
            text = " ".join(original["message"].casefold().split())
            if (utterances.setdefault(text, split) != split or text in pilot
                    or "trace-v3" in text or step["turn"] != number):
                raise ValueError("Cross-partition/pilot overlap or identifier in focal utterance")
            for candidate in step["candidates"]:
                identifier = history["id"], candidate["id"]
                if identifier in seen:
                    raise ValueError("Duplicate candidate key")
                seen.add(identifier)
                status = candidate["status"]
                if status not in ("verified", "verification_failure"):
                    if candidate["helpful"] is not None or "features" in candidate:
                        raise ValueError("Unverified candidate has features or a label")
                    abstained_rows[status] += 1
                    continue
                vector = candidate["features"]
                budget_fraction = (history["cap"] - calls) / history["cap"]
                if (len(vector) != len(FEATURE_NAMES) or any(not math.isfinite(x) for x in vector)
                        or candidate["prior_calls"] != calls or calls >= history["cap"]
                        or vector[-1] != budget_fraction or vector[2] != 1):
                    raise ValueError("Invalid or noncausal feature vector")
                calls += 1
                if status == "verification_failure":
                    if candidate["helpful"] is not None:
                        raise ValueError("Failed verifier received a label")
                    failures += 1
                    continue
                gold = original["gold"]
                expected_state = [[gold["current"].casefold()], [gold["prior"].casefold()]] if gold else None
                before, after = candidate["unverified"], candidate["verified"]
                helpful = before != expected_state and after == expected_state if gold else None
                harmful = before == expected_state and after != expected_state if gold else None
                if (candidate["gold"] != gold or candidate["helpful"] is not helpful
                        or candidate["harmful"] is not harmful
                        or candidate["unchanged"] is not (before == after)):
                    raise ValueError("Outcome disagrees with independent gold")
                projected.append({"history": history["id"], "candidate": candidate["id"], "split": split,
                                  "family": history["family"], "helpful": helpful,
                                  "features": vector[:1] + vector[2:]})
        if result["attempts"] != calls or result["failures"] != failures:
            raise ValueError("History ledger does not agree with collected candidates")
    with closing(sqlite3.connect((release / "responses.sqlite").resolve().as_uri() + "?mode=ro",
                                 uri=True)) as db:
        latencies = [t for (t,) in db.execute(
            "SELECT latency_ms FROM attempt WHERE latency_ms IS NOT NULL ORDER BY latency_ms")]
    stats = {
        "histories": len(rows), "families": len(families), "candidates": len(seen),
        "noncall_candidates": dict(abstained_rows), "pilot_text_overlap": 0,
        "provider_mean_ms": sum(latencies) / len(latencies) if latencies else None,
        "provider_p95_ms": latencies[math.ceil(0.95 * len(latencies)) - 1] if latencies else None,
        "ablation_rows": len(projected),
    }
    if ablation is not None:
        root = Path("results").resolve()
        if root not in ablation.resolve().parents:
            raise ValueError("Keep the ablation under ignored results/")
        ablation.mkdir(parents=True, exist_ok=False)
        payload = b"".join(map(encode, projected))
        save(ablation / "features.jsonl", payload)
        metadata = {"features": FEATURE_NAMES[:1] + FEATURE_NAMES[2:],
                    "source_outcomes_sha256": report["outcomes_sha256"],
                    "features_sha256": sha(payload), "rows": len(projected)}
        save(ablation / "manifest.json", encode(metadata))
        stats["ablation"] = metadata
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("release", type=Path)
    parser.add_argument("--ablation", type=Path)
    args = parser.parse_args()
    print(json.dumps(review_release(args.dataset, args.release, args.ablation), sort_keys=True))
