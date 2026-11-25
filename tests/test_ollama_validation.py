import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.export_eligible_annotations import export
from scripts.validate_ollama_verifier import CASES, verdict_gate
from trace_mem.data.updateset import generate, write_release


class OllamaValidationTest(unittest.TestCase):
    def test_verdict_gate_checks_false_updates_and_failures_separately(self):
        self.assertEqual(len(CASES), 12)
        self.assertTrue(verdict_gate(10, 0, 0))
        self.assertFalse(verdict_gate(9, 0, 0))
        self.assertFalse(verdict_gate(11, 1, 0))
        self.assertFalse(verdict_gate(11, 0, 1))

    def test_pending_export_skips_test_and_contains_no_gold(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset, output = root / "release", root / "packet.jsonl"
            settings = dict(seed=23, sizes=dict(train=7, validation=7, test=7))
            write_release(dataset, generate(**settings), **settings)
            with patch("scripts.export_eligible_annotations.Path") as paths:
                paths.return_value.resolve.return_value = root
                report = export(dataset, output)
            self.assertEqual(report["counts"], {"train": 1, "validation": 1})
            packet = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(len(packet), 2)
            for row in packet:
                self.assertEqual(set(row), {"case_id", "conversation", "old_fact", "new_claim"})
                self.assertNotIn("/test/", row["case_id"])
