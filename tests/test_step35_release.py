"""Offline release verification and fail-closed input checks."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from reproducibility.reproduce import ROOT, ReleaseError, check_row, load_rows, run, verify


class ReleaseTests(unittest.TestCase):
    def test_reproduce_all_published_conditions_and_contrasts(self):
        conditions, contrasts, history, family = run()
        self.assertEqual((len(conditions), len(contrasts), history, family), (230, 184, 27000, 2300))
        primary = {r["mode"]: r["difference"] for r in contrasts
                   if r["step"] == 30 and r["budget"] == 50 and r["left"] == "T2"
                   and r["right"] == "H-paced"}
        self.assertAlmostEqual(primary["closed-loop"], 40 / 600)
        self.assertAlmostEqual(primary["fixed"], -68 / 600)

    def test_missing_or_altered_release_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp) / "package"
            shutil.copytree(ROOT, clone, ignore=shutil.ignore_patterns("__pycache__"))
            changed = clone / "data/family.jsonl.gz"
            changed.unlink()
            with self.assertRaisesRegex(ReleaseError, "Missing release file"):
                verify(clone)
            changed.write_bytes(b"tampered")
            with self.assertRaisesRegex(ReleaseError, "SHA-256 mismatch"):
                verify(clone)

    def test_schema_rejects_source_text_ids_and_overspending(self):
        row = load_rows(ROOT / "data/history.jsonl.gz")[0]
        bad = json.loads(json.dumps(row))
        bad["transcript"] = "no"
        with self.assertRaisesRegex(ReleaseError, "Unexpected history fields"):
            check_row(bad, bad["metrics"])
        bad = dict(row, family="original-family-name")
        with self.assertRaisesRegex(ReleaseError, "anonymous"):
            check_row(bad, bad["metrics"])
        with self.assertRaisesRegex(ReleaseError, "Out-of-range count"):
            check_row(row, dict(row["metrics"], verification_attempts=row["metrics"]["budget_cap"] + 1))
