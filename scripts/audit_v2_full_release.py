"""Verify full v2 artifacts and summarize the independent support for each class."""

import argparse
from datetime import date
import json
from pathlib import Path

from scripts.collect_updateset_v2 import audit
from trace_mem.claims import Claim
from trace_mem.controller import FEATURE_NAMES, features_for
from trace_mem.data.updateset_v2 import read_release, sha
from trace_mem.memory import Fact, Source


def _source(raw: dict) -> Source:
    return Source(date.fromisoformat(raw["observed_on"]), raw["reference"])


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _verify_candidate(candidate: dict, case: dict) -> None:
    if "features" not in candidate:
        if candidate["status"] != "ineligible" or candidate["helpful"] is not None:
            raise ValueError("An eligible or labeled candidate lacks features")
        return
    c, f = candidate["claim"], candidate["target"]
    claim = Claim(c["predicate"], c["value"], c["intent"],
                  date.fromisoformat(c["effective_on"]), _date(c["expires_on"]))
    fact = Fact(f["fact_id"], f["entity"], f["predicate"], f["value"], _source(f["source"]),
                date.fromisoformat(f["valid_from"]), _date(f["valid_to"]), f["supersedes"])
    expected = features_for(claim, fact, entity=case["persona"], source=_source(candidate["source"]),
                            budget_remaining_fraction=1.0)
    if tuple(candidate["features"]) != expected or fact.fact_id != case["old_fact"]["id"]:
        raise ValueError("Candidate features or target differ from frozen input")
    if candidate["status"] == "verification_failure":
        if candidate["helpful"] is not None:
            raise ValueError("A failed verifier call has a label")
        return
    if candidate["status"] != "verified" or candidate["gold"] != case["gold"]:
        raise ValueError("Candidate gold differs from independent source")
    gold = case["gold"]
    target = [[gold["current_value"].casefold()], [gold["preserve_prior_value"].casefold()]] if gold else None
    helpful = candidate["unverified"] != target and candidate["verified"] == target if gold else None
    harmful = candidate["unverified"] == target and candidate["verified"] != target if gold else None
    if (candidate["helpful"] is not helpful or candidate["harmful"] is not harmful
            or candidate["unchanged"] is not (candidate["unverified"] == candidate["verified"])):
        raise ValueError("Stored label or change indicator disagrees with frozen gold")


def audit_release(dataset: Path, output: Path) -> dict:
    cases, manifest = read_release(dataset)
    spec = json.loads((output / "freeze.json").read_bytes())
    report = json.loads((output / "report.json").read_bytes())
    data = (output / "outcomes.jsonl").read_bytes()
    if (spec["source"] != manifest["files"] or spec["pilot_ids"] != manifest["pilot_ids"]
            or tuple(spec["feature_names"]) != FEATURE_NAMES
            or sha(data) != report["outcomes_sha256"]):
        raise ValueError("Release manifests or outcome hash disagree")
    rows = [json.loads(line) for line in data.splitlines()]
    if len(rows) != len(cases) or len(rows) != report["cases"] or audit(rows) != report["groups"]:
        raise ValueError("Release lacks cases or matches a different reported distribution")
    pilot = set(spec["pilot_ids"])
    groups = {}
    seen_ids = set()
    for case, row in zip(cases, rows):
        for field in ("case_id", "split", "family", "persona", "history"):
            if row[field] != case[field]:
                raise ValueError("Case was moved or replaced after generation")
        if row["pilot"] is not (row["case_id"] in pilot):
            raise ValueError("Pilot partition was changed")
        key = f'{row["split"]}/{"pilot" if row["pilot"] else "nonpilot"}'
        group = groups.setdefault(key, {"positive": set(), "negative": set(),
                                       "positive_families": set(), "negative_families": set(),
                                       "positive_vectors": set(), "negative_vectors": set()})
        for candidate in row["candidates"]:
            if candidate["id"] in seen_ids:
                raise ValueError("Duplicate candidate ID")
            seen_ids.add(candidate["id"])
            _verify_candidate(candidate, case)
            if candidate["helpful"] is not None:
                category = "positive" if candidate["helpful"] else "negative"
                group[category].add(row["case_id"])
                group[f"{category}_families"].add(row["family"])
                group[f"{category}_vectors"].add(tuple(candidate["features"]))
    return {
        "outcomes_sha256": report["outcomes_sha256"], "cases_verified": len(rows),
        "candidate_ids_verified": len(seen_ids),
        "class_support": {key: {name: len(items) for name, items in group.items()} | {
            "mixed_label_vectors": len(group["positive_vectors"] & group["negative_vectors"]),
        }
                          for key, group in groups.items()},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit_release(args.dataset, args.output), sort_keys=True))
