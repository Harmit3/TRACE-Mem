from dataclasses import fields
from datetime import date
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from trace_mem.baselines import run_t1
from trace_mem.data.memora import Event
from trace_mem.data.updateset import add_records, generate, read_release, write_release
from trace_mem.training import budget_threshold, collect_pairs, load_model, save_model, train
from trace_mem.semantic import NLIScores, SemanticEvidence


SETTINGS = {"seed": 23, "sizes": {"train": 14, "validation": 7, "test": 7}}


class TrainingTest(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.raw = self.root / "raw"
        write_release(self.raw, generate(**SETTINGS), **SETTINGS)

    def collect(self):
        seen = []

        def unverified(case):
            self.assertEqual({x.name for x in fields(case)}, {"old", "new", "source", "conversation"})
            self.assertNotIn("/test/", case.source.reference)
            seen.append(case)
            return {"operation": "defer", "target_id": None}

        def verified(case):
            self.assertIs(case, seen[-1])
            if case.new.intent == "correct":
                return {"operation": "supersede", "target_id": case.old.fact_id}
            return {"operation": "defer", "target_id": None}

        paired = self.root / "paired"
        report = collect_pairs(self.raw, paired, unverified=unverified, verified=verified,
                               reference="mock fixture only", origin="synthetic_mock")
        self.assertEqual(len(seen), 21)
        self.assertEqual(report["distribution"]["test"]["missing_outcomes"], 7)
        return paired

    def test_collection_fit_calibration_roundtrip_and_replay(self):
        paired = self.collect()
        data, _ = read_release(paired)
        self.assertTrue(any(row["verification_helpful"] is True for row in data))
        self.assertTrue(any(row["verification_helpful"] is False for row in data))
        with self.assertRaisesRegex(ValueError, "positive and negative"):
            train(paired, seed=7, target_fraction=0.5)
        result = train(paired, seed=7, target_fraction=0.5, allow_mock=True)
        self.assertTrue(result.report["contains_mock_outcomes"])
        self.assertEqual(result.report["training_rows"], 4)
        self.assertEqual(result.report["validation"]["rows"], 2)
        self.assertLessEqual(result.report["validation"]["selected"], 1)
        self.assertTrue(0 <= result.report["validation"]["brier"] <= 1)
        self.assertEqual(sum(b["count"] for b in result.report["validation"]["calibration_bins"]), 2)
        artifact = self.root / "model.json"
        save_model(result, artifact)
        restored = load_model(artifact)
        self.assertEqual(result, restored)
        events = [Event(date(2026, 1, i), i, 1, "user", value)
                  for i, value in enumerate(("Old", "New"), 1)]

        def complete(prompt, payload):
            value = json.loads(payload)["message"]
            return json.dumps([dict(predicate="job", value=value, intent="correct")])

        replayed = run_t1(events, complete, entity="p", controller=restored.controller,
                          calls=1, threshold=restored.threshold, verify=lambda *_: "update")
        self.assertEqual(replayed.attempts, 1)
        self.assertEqual(replayed.memory.trace[-1].operation, "supersede")
        payload = json.loads(artifact.read_bytes())
        payload["features"].reverse()
        artifact.write_text(json.dumps(payload))
        with self.assertRaisesRegex(ValueError, "feature order"):
            load_model(artifact)

    def test_train_only_scaling_and_test_outcome_isolation(self):
        paired = self.collect()
        rows, _ = read_release(paired)
        test_case = next(r for r in rows if r["split"] == "test" and r["category"] == "correction")
        variant = self.root / "test-changed"
        with_test = add_records(rows, [{"case_id": test_case["case_id"], "outcomes": {
            "origin": "recorded_verifier", "reference": "test fixture",
            "unverified": {"operation": "defer", "target_id": None},
            "verified": {"operation": "supersede", "target_id": test_case["old_fact"]["fact_id"]},
        }}], field="outcomes")
        write_release(variant, with_test, **SETTINGS)

        def infer(old, new):
            if "/test/" in old or "/test/" in new:
                self.fail("Test features must not be built during training")
            score = 0.9 if "/validation/" in old else 0.1
            return NLIScores(score, 1 - score, 0)

        semantic = SemanticEvidence(lambda texts: [[1, 0]] * len(texts), infer)
        kwargs = dict(seed=7, target_fraction=0.5, allow_mock=True,
                      semantic=semantic, semantic_reference="mock NLI")
        first, second = train(paired, **kwargs), train(variant, **kwargs)
        self.assertAlmostEqual(first.controller.means[1], 0.1)
        self.assertEqual(first.controller, second.controller)
        self.assertEqual(first.threshold, second.threshold)
        self.assertEqual(first.report["validation"], second.report["validation"])

    def test_budget_threshold_handles_ties_zero_and_invalid_inputs(self):
        self.assertEqual(budget_threshold([0.8, 0.8, 0.4], 0.5), 1.0)
        self.assertEqual(budget_threshold([0.8, 0.8, 0.4], 0.7), 0.8)
        self.assertEqual(budget_threshold([0.8], 0), 1.0)
        for scores, limit in (([float("nan")], 1), ([0.5], 1.1)):
            with self.assertRaises(ValueError):
                budget_threshold(scores, limit)

    def test_unlabeled_dataset_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "train requires"):
            train(self.raw, seed=7, target_fraction=0.5)

    def test_collection_failure_leaves_no_partial_release(self):
        output = self.root / "failed"

        def fail(case):
            raise TimeoutError("fixture timeout")

        with self.assertRaises(TimeoutError):
            collect_pairs(self.raw, output, unverified=lambda case: {"operation": "defer", "target_id": None},
                          verified=fail, reference="fixture only", origin="synthetic_mock")
        self.assertFalse(output.exists())
