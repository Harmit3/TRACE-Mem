from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from trace_mem.data.updateset import (
    SPLITS, add_records, annotation_packet, generate, read_release, validate, write_release,
)


SETTINGS = {"seed": 23, "sizes": dict.fromkeys(SPLITS, 7)}


def decision(operation, target_id=None):
    return {"operation": operation, "target_id": target_id}


def outcome(row, unverified, verified):
    return {"case_id": row["case_id"], "outcomes": {
        "origin": "synthetic_mock", "reference": "unit-test-fixture",
        "unverified": unverified, "verified": verified,
    }}


class UpdateSetTest(unittest.TestCase):
    def setUp(self):
        self.rows = generate(**SETTINGS)

    def test_reproducible_balanced_categories_and_disjoint_groups(self):
        self.assertEqual(self.rows, generate(**SETTINGS))
        self.assertNotEqual(self.rows, generate(24, SETTINGS["sizes"]))
        summary = validate(self.rows, **SETTINGS)
        for split in SPLITS:
            items = [row for row in self.rows if row["split"] == split]
            self.assertEqual(Counter(row["category"] for row in items), {
                "correction": 1, "contradiction": 1, "outdated": 1, "historical": 1,
                "temporary": 1, "ambiguous": 1, "deletion": 1,
            })
            self.assertEqual(summary[split]["synthetic_rule"], 6)
            self.assertEqual(summary[split]["pending_label"], 7)
        for key in ("persona_id", "history_id", "scenario_family"):
            groups = [{row[key] for row in self.rows if row["split"] == split} for split in SPLITS]
            self.assertEqual(sum(map(len, groups)), len(set.union(*groups)))

    def test_helpfulness_requires_incorrect_to_correct_with_exact_target(self):
        row = next(row for row in self.rows if row["category"] == "correction")
        gold = row["gold"]["decision"]
        wrong = decision("add")
        for before, after, expected in ((wrong, gold, True), (gold, gold, False),
                                         (gold, wrong, False), (wrong, wrong, False)):
            with self.subTest(before=before, after=after):
                updated = add_records(self.rows, [outcome(row, before, after)], field="outcomes")
                matched = next(r for r in updated if r["case_id"] == row["case_id"])
                self.assertIs(matched["verification_helpful"], expected)
                self.assertEqual(validate(updated, **SETTINGS)[row["split"]][
                    "helpful" if expected else "not_helpful"], 1)
        with self.assertRaises(ValueError):
            add_records(self.rows, [outcome(row, wrong, decision("supersede", "bad-id"))],
                        field="outcomes")

    def test_annotation_packet_is_blind_and_pending_gold_delays_label(self):
        pending = next(row for row in self.rows if row["gold"] is None)
        with_outcomes = add_records(self.rows, [outcome(pending, decision("add"), decision("defer"))],
                                    field="outcomes")
        self.assertEqual(len(annotation_packet(with_outcomes)), 3)
        packet = annotation_packet(with_outcomes)[0]
        self.assertEqual(set(packet), {"case_id", "conversation", "old_fact", "new_claim"})
        self.assertIsNone(next(row for row in with_outcomes
                               if row["case_id"] == pending["case_id"])["verification_helpful"])
        # Mock the annotation format in an ephemeral test only.
        annotation = {"case_id": pending["case_id"], "gold": {
            "origin": "human_annotation", "reference": "mock-test-only", "decision": decision("defer"),
        }}
        rows = add_records(with_outcomes, [annotation], field="gold")
        self.assertEqual(len(annotation_packet(rows)), 2)
        self.assertEqual(validate(rows, **SETTINGS)[pending["split"]]["helpful"], 1)
        with self.assertRaises(ValueError):
            add_records(rows, [annotation], field="gold")

    def test_validation_detects_duplicates_leakage_and_modified_inputs(self):
        mutations = [
            ("Duplicate case", lambda r: r[1].update(case_id=r[0]["case_id"])),
            ("Duplicate conversation", lambda r: r[1].update(conversation=r[0]["conversation"])),
            ("independent synthetic", lambda r: r[0]["new_claim"].update(value="foreign answer")),
            ("helpfulness disagrees", lambda r: r[0].update(verification_helpful=False)),
        ]
        for field in ("persona_id", "history_id", "scenario_family"):
            mutations.append((f"leakage in {field}",
                              lambda r, key=field: r[7].update({key: r[0][key]})))
        for error, mutate in mutations:
            rows = deepcopy(self.rows)
            mutate(rows)
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                validate(rows, **SETTINGS)

    def test_empty_release_and_invalid_generation_settings(self):
        sizes = dict.fromkeys(SPLITS, 0)
        self.assertEqual(validate(generate(0, sizes), seed=0, sizes=sizes)["test"]["rows"], 0)
        with self.assertRaises(ValueError):
            generate(True, sizes)
        with self.assertRaises(ValueError):
            generate(0, {"train": -1, "validation": 0, "test": 0})

    def test_release_hash_and_byte_reproducibility(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, b = root / "a", root / "b"
            self.assertEqual(write_release(a, self.rows, **SETTINGS),
                             write_release(b, self.rows, **SETTINGS))
            self.assertEqual(read_release(a)[0], self.rows)
            self.assertEqual((a / "cases.jsonl").read_bytes(), (b / "cases.jsonl").read_bytes())
            (a / "cases.jsonl").write_text("tampered")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                read_release(a)

    def test_cli_generate_validate_and_import_outcomes(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)

            def cli(*args):
                result = subprocess.run([sys.executable, "-m", "trace_mem.data.updateset", *map(str, args)],
                                        check=True, capture_output=True, text=True)
                return json.loads(result.stdout)

            raw = root / "raw"
            manifest = cli("generate", raw, "--seed", 23, "--train", 7, "--validation", 7, "--test", 7)
            self.assertEqual(manifest, cli("validate", raw))
            self.assertEqual(cli("annotation-packet", raw, root / "packet.jsonl"), {"pending_cases": 3})
            row = next(row for row in self.rows if row["category"] == "deletion")
            sidecar = root / "outcomes.jsonl"
            sidecar.write_text(json.dumps(outcome(row, decision("defer"), row["gold"]["decision"])))
            joined = cli("import-outcomes", raw, root / "joined", "--records", sidecar)
            self.assertEqual(joined["distribution"][row["split"]]["helpful"], 1)
            self.assertEqual(joined["lineage"]["operation"], "import-outcomes")
            self.assertEqual(joined, cli("validate", root / "joined"))
