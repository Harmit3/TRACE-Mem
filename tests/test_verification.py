from datetime import date
import unittest

from trace_mem.claims import Claim
from trace_mem.memory import Fact, Source
from trace_mem.verification import Budget, select_random, select_ranked


class VerificationTest(unittest.TestCase):
    def test_selectors_match_and_break_ties(self):
        scores = [0.2, 0.9, 0.9, 0.9]
        for calls in (0, 1, 2, 4):
            self.assertEqual(len(select_random(4, calls, seed=7)), len(select_ranked(scores, calls)))
        self.assertEqual(select_ranked(scores, 2), {1, 2})
        self.assertEqual(select_random(4, 2, seed=7), select_random(4, 2, seed=7))
        with self.assertRaises(ValueError):
            select_random(4, 5, seed=7)

    def test_failed_attempt_consumes_budget(self):
        day = date(2026, 1, 1)
        claim = Claim("job", "new", "uncertain", day)
        fact = Fact("a", "person", "job", "old", Source(day, "source"), day)
        budget = Budget(1)

        def timeout(*args):
            raise TimeoutError

        self.assertEqual(budget.call(timeout, claim, fact), "insufficient_evidence")
        self.assertEqual((budget.attempts, budget.failures, budget.remaining), (1, 1, 0))
        with self.assertRaises(RuntimeError):
            budget.call(timeout, claim, fact)
