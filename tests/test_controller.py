import unittest

from trace_mem.controller import fit
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
