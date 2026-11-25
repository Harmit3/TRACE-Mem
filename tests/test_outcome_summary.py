from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from scripts.summarize_updateset_outcomes import summarize
from trace_mem.data.updateset import add_records, generate, write_release
from trace_mem.training import _inputs, eligible_case


class OutcomeSummaryTest(unittest.TestCase):
    def test_counts_only_verified_release_outcomes_and_rejects_test_changes(self):
        settings = {"seed": 23, "sizes": {"train": 7, "validation": 7, "test": 7}}
        rows = generate(**settings)
        fixture_records = []
        for row in rows:
            if not eligible_case(_inputs(row)):
                continue
            defer = {"operation": "defer", "target_id": None}
            fixture_records.append({"case_id": row["case_id"], "outcomes": {
                "origin": "recorded_verifier", "reference": "test fixture only",
                "unverified": defer, "verified": defer,
            }})
        test_ids = {row["case_id"] for row in rows if row["split"] == "test"}
        train_validation = [row for row in fixture_records if row["case_id"] not in test_ids]
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            initial = write_release(root / "source", rows, **settings)
            lineage = {"parent_cases_sha256": initial["files"]["cases.jsonl"]}
            write_release(root / "paired", add_records(rows, train_validation, field="outcomes"),
                          lineage=lineage, **settings)
            write_release(root / "invalid", add_records(rows, fixture_records, field="outcomes"),
                          lineage=lineage, **settings)
            packet = root / "packet.jsonl"
            packet.write_bytes(b"fixture")
            ledger = root / "ledger.sqlite"
            with closing(sqlite3.connect(ledger)) as db, db:
                db.executescript("""
                    CREATE TABLE attempt (status, input_tokens, output_tokens, latency_ms, cost, model);
                    CREATE TABLE cache_hit (id);
                    INSERT INTO attempt VALUES ('ok', 3, 2, 20.0, 0, 'fixture');
                    INSERT INTO attempt VALUES ('unknown', NULL, NULL, 15.0, 0, NULL);
                """)
            summary = summarize(root / "source", root / "paired", ledger, packet)
            self.assertEqual(summary["split_counts"]["train"],
                             dict(eligible=3, pairs=3, positive=0, negative=2, pending_gold=1))
            self.assertEqual(summary["split_counts"]["validation"]["pairs"], 3)
            self.assertEqual(summary["split_counts"]["test"]["pairs"], 0)
            self.assertEqual(summary["failures"], 1)
            self.assertEqual(summary["success_latency_ms"]["p95"], 20.0)
            self.assertFalse(summary["training_ready"])
            with self.assertRaisesRegex(ValueError, "Test or ineligible"):
                summarize(root / "source", root / "invalid", ledger, packet)
