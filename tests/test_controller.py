from datetime import date
import unittest

from trace_mem.claims import Claim
from trace_mem.controller import FEATURE_NAMES, LogisticController, features_for, fit
from trace_mem.memory import Fact, Source
from trace_mem.verification import select_random, select_ranked


class ControllerTest(unittest.TestCase):
    def test_training_is_deterministic_and_selection_matches_random_calls(self):
        rows = [(0.1, 1), (0.2, 1), (0.8, 1), (0.9, 1)]
        labels = [0, 0, 1, 1]
        controller = fit(rows, labels)
        self.assertEqual(controller, fit(rows, labels))
        self.assertEqual(controller.scales[1], 1.0)
        scores = [controller.score(row) for row in rows]
        self.assertLess(scores[0], 0.5)
        self.assertGreater(scores[-1], 0.5)
        selected = select_ranked(scores, 2)
        self.assertEqual(selected, {2, 3})
        self.assertEqual(len(selected), len(select_random(len(rows), 2, seed=7)))

    def test_rejects_nonfinite_training_features(self):
        with self.assertRaises(ValueError):
            fit([(0.1,), (float("nan"),)], [0, 1])

    def test_readme_feature_order_and_values(self):
        old, new = date(2026, 3, 1), date(2026, 3, 6)
        target = Fact("a", "p", "job", "Alder Labs", Source(old, "1/1"), old)
        claim = Claim("job", "Birch Labs", "uncertain", new)
        expected = {
            "semantic_similarity": 1 / 3, "contradiction_score": 0.5, "entity_match": 1.0,
            "temporal_conflict_score": 1.0, "time_gap": 5.0, "provenance_score": 1.0,
            "uncertainty": 1.0, "budget_remaining_fraction": 0.25,
        }
        self.assertEqual(FEATURE_NAMES, tuple(expected))
        self.assertEqual(features_for(claim, target, entity="p", source=Source(new, "2/1"),
                                      budget_remaining_fraction=0.25), tuple(expected.values()))
        for invalid in (-0.1, 1.1, float("nan")):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                features_for(claim, target, entity="p", source=Source(new, "2/1"),
                             budget_remaining_fraction=invalid)
        with self.assertRaisesRegex(ValueError, "future observation"):
            features_for(claim, target, entity="p", source=Source(date(2026, 2, 28), "0/1"),
                         budget_remaining_fraction=1)

    def test_invalid_parameters_and_feature_width(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            LogisticController((0,), (0,), (1,), 0)
        with self.assertRaisesRegex(ValueError, "finite"):
            LogisticController((0,), (1,), (float("inf"),), 0)
        with self.assertRaisesRegex(ValueError, "width"):
            LogisticController((0,), (1,), (1,), 0).score(())
