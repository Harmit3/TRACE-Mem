import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.export_eligible_annotations import export
from scripts.validate_ollama_verifier import CASES, verdict_gate
from scripts import validate_ollama_verifier_v2 as revised
from scripts import compare_local_verifiers as comparison
from trace_mem.claims import Claim
from trace_mem.data.updateset import generate, write_release
from trace_mem.llm_tasks import LLMTasks, MockProvider
from trace_mem.memory import Fact, Source


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

    def test_fresh_cases_and_gate(self):
        self.assertEqual(len(revised.CASES), 40)
        self.assertEqual(len({row[5] for row in revised.CASES}), 40)
        self.assertFalse({row[6] for row in CASES} & {row[5] for row in revised.CASES})
        self.assertTrue(revised.gate(37, 0, 0, 13 / 16))
        self.assertFalse(revised.gate(36, 0, 0, 12 / 16))
        self.assertFalse(revised.gate(39, 1, 0, 1))
        self.assertFalse(revised.gate(39, 0, 1, 1))

    def test_model_comparison_uses_disjoint_cases_and_original_gate(self):
        cases = comparison.CASES
        self.assertEqual(len(cases), 40)
        self.assertEqual(sum(row[-1] for row in cases), 16)
        self.assertEqual(len({row[5] for row in cases}), len(cases))
        self.assertFalse({row[5] for row in cases} & {row[5] for row in revised.CASES})
        self.assertFalse({row[5] for row in cases} & {row[6] for row in CASES})

    def test_grounded_confirmed_quote_required_for_two_stage_update(self):
        day = date(2026, 2, 15)
        old = Fact("old", "user", "job", "Alder", Source(day, "session/1"), day)
        claim = Claim("job", "Birch", "correct", day)
        message = "I have switched to Birch."
        for kind, quote, expected in (
            ("confirmed_replacement", message, "update"),
            ("confirmed_replacement", "invented quote", "insufficient_evidence"),
            ("hypothetical", message, "insufficient_evidence"),
        ):
            requests = []

            def respond(task, payload):
                requests.append((task, json.loads(payload)))
                if task == "verify-evidence-v2":
                    return json.dumps({"kind": kind, "quote": quote})
                return '{"verdict":"update"}'

            with self.subTest(kind=kind, quote=quote):
                tasks = LLMTasks(MockProvider(respond), verification_mode="evidence-v2")
                self.assertEqual(tasks.verify(claim, old, conversation=(message,)), expected)
                self.assertEqual([t for t, _ in requests],
                                 ["verify-evidence-v2", "verify-evidence-verdict-v2"])
                if quote != message:
                    self.assertIsNone(requests[1][1]["extracted"]["quote"])
