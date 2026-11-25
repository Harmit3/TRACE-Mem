"""Generate and validate independent synthetic TRACE-UpdateSet artifacts."""

import argparse
from collections import Counter
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import random
from typing import Any


SPLITS = ("train", "validation", "test")
VERSION = 1

# Each split owns distinct templates. Broad operation categories recur so that
# the task is shared, but scenarios, source histories and personas do not.
# Fields: category, predicate, old value, new value, utterance, intent, gold.
SCENARIOS = {
    "train": (
        ("correction", "job", "Alder Lab", "Birch Lab", "I now work at {new}.", "correct", "supersede"),
        ("contradiction", "residence", "Oak Town", "Pine Town", "I live in {new}.", "assert", "defer"),
        ("outdated", "pass", "Spring Badge", "Summer Badge", "My active pass is {new}.", "assert", "add"),
        ("historical", "job", "Current Lab", "Archive Lab", "Before this I worked at {new}.", "assert", "historical"),
        ("temporary", "residence", "Home City", "Camp City", "I am visiting {new} this weekend.", "assert", "add"),
        ("ambiguous", "job", "North Office", "South Office", "Things might shift toward {new}.", "uncertain", None),
        ("deletion", "residence", "Cove Town", "", "Forget that I lived in {old}.", "delete", "delete"),
    ),
    "validation": (
        ("correction", "commute", "Blue Route", "Red Route", "My commute switched to {new}.", "correct", "supersede"),
        ("contradiction", "membership", "Morning Club", "Evening Club", "My only club is {new}.", "assert", "defer"),
        ("outdated", "permit", "Winter Permit", "Autumn Permit", "The valid permit now is {new}.", "assert", "add"),
        ("historical", "residence", "Bay Town", "Hill Town", "I used to live in {new} before moving.", "assert", "historical"),
        ("temporary", "worksite", "Main Campus", "Field Cabin", "For two days I am stationed at {new}.", "assert", "add"),
        ("ambiguous", "commute", "River Line", "Park Line", "Maybe {new} takes over next month.", "uncertain", None),
        ("deletion", "membership", "Elm Guild", "", "Remove the record of my membership in {old}.", "delete", "delete"),
    ),
    "test": (
        ("correction", "worksite", "West Depot", "East Depot", "I transferred permanently to {new}.", "correct", "supersede"),
        ("contradiction", "subscription", "Print Plan", "Digital Plan", "The only plan I have is {new}.", "assert", "defer"),
        ("outdated", "access_card", "Copper Card", "Silver Card", "The card that works today is {new}.", "assert", "add"),
        ("historical", "commute", "South Loop", "North Loop", "Before this route I used {new}.", "assert", "historical"),
        ("temporary", "training_site", "Local Studio", "Guest Studio", "I have a two-day workshop at {new}.", "assert", "add"),
        ("ambiguous", "subscription", "Weekly Edition", "Daily Edition", "I might end up with {new}.", "uncertain", None),
        ("deletion", "worksite", "Marsh Station", "", "Erase the stored detail that I worked at {old}.", "delete", "delete"),
    ),
}
OPERATIONS = {"add", "supersede", "historical", "defer", "delete"}
TARGETED = {"supersede", "delete"}


def _encode(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def generate(seed: int, sizes: dict[str, int]) -> list[dict]:
    if type(seed) is not int or set(sizes) != set(SPLITS) or any(
        type(size) is not int or size < 0 for size in sizes.values()
    ):
        raise ValueError("Expected an integer seed and nonnegative sizes for train, validation and test")
    rng = random.Random(seed)
    rows = []
    for split in SPLITS:
        order = list(SCENARIOS[split])
        rng.shuffle(order)
        for index in range(sizes[split]):
            category, predicate, old, new, message, intent, gold = order[index % len(order)]
            case_id = f"trace-synthetic-v{VERSION}/{seed}/{split}/{index}"
            history = f"{case_id}/history"
            observed = date(2025, 1, 20) + timedelta(days=rng.randrange(365))
            old_start = observed - timedelta(days=10)
            suffix = f" {index}-{rng.randrange(10000):04d}"
            old += suffix
            new = new + suffix if new else old
            old_id = f"{history}/fact/1"
            explain = message.format(old=old, new=new)
            claim_start = old_start - timedelta(days=7) if category == "historical" else observed
            old_end = observed - timedelta(days=1) if category == "outdated" else None
            claim_end = (old_start if category == "historical" else
                         observed + timedelta(days=2) if category == "temporary" else None)
            new_predicate = f"temporary_{predicate}" if category == "temporary" else predicate
            proposed = {"correct": "supersede", "assert": "add",
                        "uncertain": "defer", "delete": "delete"}[intent]
            rows.append({
                "case_id": case_id,
                "split": split,
                "persona_id": f"{case_id}/persona",
                "scenario_family": f"trace-synthetic-v{VERSION}/{split}/{category}-{predicate}",
                "category": category,
                "history_id": history,
                "origin": "trace_synthetic",
                "conversation": [
                    {"observed_on": old_start.isoformat(), "source_ref": f"{history}/1",
                     "text": f"My {predicate} is {old}."},
                    {"observed_on": observed.isoformat(), "source_ref": f"{history}/2", "text": explain},
                ],
                "old_fact": {"fact_id": old_id, "predicate": predicate, "value": old,
                             "valid_from": old_start.isoformat(),
                             "valid_to": old_end.isoformat() if old_end else None,
                             "observed_on": old_start.isoformat(), "source_ref": f"{history}/1"},
                "new_claim": {"predicate": new_predicate, "value": new, "intent": intent,
                              "effective_on": claim_start.isoformat(),
                              "expires_on": claim_end.isoformat() if claim_end else None,
                              "observed_on": observed.isoformat(), "source_ref": f"{history}/2"},
                "proposal": _decision(proposed, old_id),
                "gold": ({"origin": "synthetic_rule", "reference": f"rules-v{VERSION}/{category}",
                          "decision": _decision(gold, old_id)} if gold is not None else None),
                "outcomes": None,
                "verification_helpful": None,
            })
    return rows


def _decision(operation: str, old_id: str) -> dict:
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise ValueError("Unknown memory operation")
    return {"operation": operation, "target_id": old_id if operation in TARGETED else None}


def _validate_decision(decision: dict, old_id: str) -> None:
    if not isinstance(decision, dict) or decision != _decision(decision.get("operation"), old_id):
        raise ValueError("Decision must contain a recognized operation and its required target")


def helpfulness(gold: dict | None, outcomes: dict | None) -> bool | None:
    if gold is None or outcomes is None:
        return None
    expected = gold["decision"]
    return outcomes["unverified"] != expected and outcomes["verified"] == expected


def annotation_packet(rows: list[dict]) -> list[dict]:
    """Expose only case inputs to an annotator."""
    fields = ("case_id", "conversation", "old_fact", "new_claim")
    return [{field: row[field] for field in fields} for row in rows if row["gold"] is None]


def add_records(rows: list[dict], records: list[dict], *, field: str) -> list[dict]:
    if field not in ("gold", "outcomes"):
        raise ValueError("Expected gold or outcomes")
    by_id = {row["case_id"]: row for row in rows}
    additions = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Sidecar entries must be objects")
        case_id = record.get("case_id")
        if case_id not in by_id or case_id in additions or by_id[case_id][field] is not None:
            raise ValueError("Unknown, duplicate or already populated case ID")
        if set(record) != {"case_id", field} or not isinstance(record[field], dict):
            raise ValueError("Invalid sidecar record")
        value = record[field]
        old_id = by_id[case_id]["old_fact"]["fact_id"]
        if field == "gold":
            _check_metadata(value, {"decision"}, {"human_annotation"})
            _validate_decision(value["decision"], old_id)
        else:
            _check_metadata(value, {"unverified", "verified"}, {"synthetic_mock", "recorded_verifier"})
            _validate_decision(value["unverified"], old_id)
            _validate_decision(value["verified"], old_id)
        additions[case_id] = value
    updated = []
    for row in rows:
        item = {**row, field: additions.get(row["case_id"], row[field])}
        item["verification_helpful"] = helpfulness(item["gold"], item["outcomes"])
        updated.append(item)
    return updated


def validate(rows: list[dict], *, seed: int, sizes: dict[str, int]) -> dict:
    reference = generate(seed, sizes)
    if len(rows) != len(reference):
        raise ValueError("Row count does not match generation settings")
    counts = {split: Counter() for split in SPLITS}
    gold_classes = {split: Counter() for split in SPLITS}
    groups = {field: {} for field in ("persona_id", "scenario_family", "history_id")}
    ids = set()
    fingerprints = set()
    for row, expected in zip(rows, reference):
        if not isinstance(row, dict) or set(row) != set(expected):
            raise ValueError("Unexpected dataset row schema")
        case_id = row["case_id"]
        if not all(isinstance(row[key], str) and row[key]
                   for key in ("case_id", "split", *groups)):
            raise ValueError("Expected nonempty case and group identifiers")
        if case_id in ids:
            raise ValueError("Duplicate case ID")
        ids.add(case_id)
        split = row["split"]
        if split not in SPLITS:
            raise ValueError("Unknown dataset split")
        for field, seen in groups.items():
            if seen.setdefault(row[field], split) != split:
                raise ValueError(f"Cross-split leakage in {field}")
        conversation = row["conversation"]
        if not isinstance(conversation, list) or any(
            not isinstance(turn, dict) or not isinstance(turn.get("text"), str) for turn in conversation
        ):
            raise ValueError("Invalid conversation text")
        fingerprint = tuple(" ".join(turn["text"].casefold().split()) for turn in conversation)
        if fingerprint in fingerprints:
            raise ValueError("Duplicate conversation content")
        fingerprints.add(fingerprint)
        mutable = {"gold", "outcomes", "verification_helpful"}
        if any(row[key] != expected[key] for key in row.keys() - mutable):
            raise ValueError("Case differs from independent synthetic generation")
        old_id = row["old_fact"]["fact_id"]
        gold, outcomes = row["gold"], row["outcomes"]
        if expected["gold"] is not None and gold != expected["gold"]:
            raise ValueError("Synthetic rule gold cannot be overridden")
        if gold is not None:
            allowed_origin = "synthetic_rule" if expected["gold"] else "human_annotation"
            _check_metadata(gold, {"decision"}, {allowed_origin})
            _validate_decision(gold["decision"], old_id)
            gold_classes[split][gold["decision"]["operation"]] += 1
        if outcomes is not None:
            _check_metadata(outcomes, {"unverified", "verified"}, {"synthetic_mock", "recorded_verifier"})
            _validate_decision(outcomes["unverified"], old_id)
            _validate_decision(outcomes["verified"], old_id)
        label = helpfulness(gold, outcomes)
        if row["verification_helpful"] is not label:
            raise ValueError("Stored helpfulness disagrees with independent decision comparison")
        counts[split]["rows"] += 1
        counts[split][gold["origin"] if gold else "pending_gold"] += 1
        counts[split]["missing_outcomes" if outcomes is None else outcomes["origin"]] += 1
        counts[split]["pending_label" if label is None else "helpful" if label else "not_helpful"] += 1
    return {split: {"rows": 0, **counts[split], "gold_operations": dict(gold_classes[split])}
            for split in SPLITS}


def _check_metadata(record: dict, fields: set[str], origins: set[str]) -> None:
    if (not isinstance(record, dict) or set(record) != fields | {"origin", "reference"}
            or record["origin"] not in origins or not isinstance(record["reference"], str)
            or not record["reference"].strip()):
        raise ValueError("Invalid record provenance")


def _generator_sha() -> str:
    return _sha(Path(__file__).read_text(encoding="utf-8").encode("utf-8"))


def write_release(directory: Path, rows: list[dict], *, seed: int, sizes: dict[str, int],
                  lineage: dict | None = None) -> dict:
    distribution = validate(rows, seed=seed, sizes=sizes)
    content = b"".join(_encode(row) + b"\n" for row in rows)
    manifest = {
        "schema_version": VERSION,
        "generator": "trace_mem.data.updateset",
        "generator_sha256": _generator_sha(),
        "origin": "trace_synthetic",
        "benchmark_inputs": [],
        "settings": {"seed": seed, "sizes": sizes},
        "files": {"cases.jsonl": _sha(content)},
        "distribution": distribution,
        "lineage": lineage,
    }
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "cases.jsonl").write_bytes(content)
    (directory / "manifest.json").write_bytes(_encode(manifest) + b"\n")
    return manifest


def read_release(directory: Path) -> tuple[list[dict], dict]:
    manifest = json.loads((directory / "manifest.json").read_bytes())
    if (manifest["schema_version"] != VERSION or manifest["origin"] != "trace_synthetic"
            or manifest["generator"] != "trace_mem.data.updateset"
            or manifest["generator_sha256"] != _generator_sha()
            or manifest["benchmark_inputs"] != []):
        raise ValueError("Unsupported dataset manifest")
    data = (directory / "cases.jsonl").read_bytes()
    if manifest["files"] != {"cases.jsonl": _sha(data)}:
        raise ValueError("Dataset hash mismatch")
    rows = [json.loads(line) for line in data.splitlines()]
    if validate(rows, **manifest["settings"]) != manifest["distribution"]:
        raise ValueError("Manifest distribution mismatch")
    return rows, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("generate")
    create.add_argument("output", type=Path)
    create.add_argument("--seed", type=int, required=True)
    for split in SPLITS:
        create.add_argument(f"--{split}", type=int, required=True)
    for command in ("validate", "annotation-packet", "import-gold", "import-outcomes"):
        task = sub.add_parser(command)
        task.add_argument("dataset", type=Path)
        if command != "validate":
            task.add_argument("output", type=Path)
        if command.startswith("import-"):
            task.add_argument("--records", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "generate":
            sizes = {split: getattr(args, split) for split in SPLITS}
            report = write_release(args.output, generate(args.seed, sizes), seed=args.seed, sizes=sizes)
        else:
            rows, report = read_release(args.dataset)
            if args.command == "annotation-packet":
                packet = annotation_packet(rows)
                with args.output.open("xb") as file:
                    for row in packet:
                        file.write(_encode(row) + b"\n")
                print(json.dumps({"pending_cases": len(packet)}))
                return
            if args.command.startswith("import-"):
                raw = args.records.read_bytes()
                rows = add_records(rows, [json.loads(line) for line in raw.splitlines()],
                                   field=args.command.removeprefix("import-"))
                lineage = {"parent_manifest_sha256": _sha((args.dataset / "manifest.json").read_bytes()),
                           "sidecar_sha256": _sha(raw), "operation": args.command}
                report = write_release(args.output, rows, lineage=lineage, **report["settings"])
        print(json.dumps(report, sort_keys=True))
    except (OSError, TypeError, ValueError, KeyError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
