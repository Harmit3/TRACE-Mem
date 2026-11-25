from datetime import date
import json
import unittest

from trace_mem.baselines import run_baseline
from trace_mem.data.memora import Event


class BaselineTest(unittest.TestCase):
    def test_replay_uses_same_claims_for_append_and_temporal_policies(self):
        events = [Event(date(2026, 3, i), i, 1, "user", str(i)) for i in range(1, 6)]
        claims = [
            ("job", "Alder", "assert"),
            ("job", "Birch", "uncertain"),
            ("job", "Birch", "correct"),
            ("job", "Alder", "delete"),
            ("job", "Cedar", "assert"),
        ]

        def cached_completion(prompt, payload):
            predicate, value, intent = claims[int(json.loads(payload)["message"]) - 1]
            return json.dumps([dict(predicate=predicate, value=value, intent=intent)])

        memories = {method: run_baseline(events, cached_completion, entity="p", method=method)
                    for method in ("B1", "B2")}
        for memory in memories.values():
            self.assertEqual(memory.retrieve("p", "job", as_of=date(2026, 3, 1)), ())
        day = date(2026, 3, 5)
        self.assertEqual({f.value for f in memories["B1"].retrieve("p", "job", as_of=day)},
                         {"Birch", "Cedar"})
        self.assertEqual([f.value for f in memories["B2"].retrieve("p", "job", as_of=day)],
                         ["Birch"])
        repeated = run_baseline(events, cached_completion, entity="p", method="B2")
        self.assertEqual(repeated.trace, memories["B2"].trace)
