from datetime import date
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from trace_mem.baselines import run_baseline, run_matched_baselines
from trace_mem.data.memora import Event, replay
from trace_mem.verification import Budget


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

    def test_verifier_update_and_failure_have_distinct_transitions(self):
        first, second = date(2026, 3, 1), date(2026, 3, 2)
        events = [Event(first, 1, 1, "user", "Alder"), Event(second, 2, 1, "user", "Birch")]

        def cached_completion(prompt, payload):
            value = json.loads(payload)["message"]
            return json.dumps([dict(predicate="job", value=value,
                                    intent="assert" if value == "Alder" else "uncertain")])

        def failure(*args):
            raise TimeoutError

        for verifier, expected in ((lambda *args: "update", "Birch"), (failure, "Alder")):
            with self.subTest(expected=expected):
                budget = Budget(1)
                memory = run_baseline(events, cached_completion, entity="p", method="B2",
                                      budget=budget, should_verify=lambda *args: True, verify=verifier)
                current, = memory.retrieve("p", "job", as_of=second)
                self.assertEqual(current.value, expected)
                self.assertEqual(budget.attempts, 1)


class MatchedBaselineTest(unittest.TestCase):
    def setUp(self):
        self.events = [
            Event(date(2026, 3, index), index, 1, "user", message)
            for index, message in enumerate(("Alder", "Birch", "Cedar", "Dogwood"), 1)
        ]
        self.extracted = []
        self.invoked = []

    def complete(self, prompt, payload):
        value = json.loads(payload)["message"]
        self.extracted.append(value)
        intents = {"Alder": "assert", "Birch": "assert", "Cedar": "uncertain", "Dogwood": "uncertain"}
        return json.dumps([{"predicate": "job", "value": value, "intent": intents[value]}])

    def verify(self, claim, target):
        self.invoked.append((claim.value, target.value))
        return "update"

    def run_pair(self, calls, *, events=None, verify=None):
        return run_matched_baselines(
            self.events if events is None else events, self.complete, entity="p",
            calls=calls, seed=2, verify=self.verify if verify is None else verify,
        )

    def test_memora_replay_selects_equal_calls_in_chronological_order(self):
        with TemporaryDirectory() as temp:
            history = Path(temp) / "synthetic"
            directory = history / "conversations"
            directory.mkdir(parents=True)
            for event in reversed(self.events):
                record = {"session_id": event.session_id, "date": event.observed_on.isoformat(),
                          "persona": history.name, "operation": "scorer-only",
                          "conversation": [{"turn": 1, "speaker": "user_agent",
                                            "message": event.message}]}
                (directory / f"session_{event.session_id}.json").write_text(json.dumps(record))
            runs = self.run_pair(2, events=replay(history))
        self.assertEqual(self.extracted, ["Alder", "Birch", "Cedar", "Dogwood"])
        self.assertEqual(runs["B4"].selected_ids, ("2/1/0", "4/1/0"))
        self.assertEqual(runs["B5"].selected_ids, ("3/1/0", "4/1/0"))
        self.assertEqual(self.invoked, [("Birch", "Alder"), ("Dogwood", "Alder"),
                                       ("Cedar", "Alder"), ("Dogwood", "Alder")])
        for method, value in (("B4", "Birch"), ("B5", "Cedar")):
            run = runs[method]
            self.assertEqual((run.attempts, run.failures, run.stale_targets), (2, 0, 1))
            current, = run.memory.retrieve("p", "job", as_of=date(2026, 3, 4))
            self.assertEqual(current.value, value)
        repeat = self.run_pair(2)
        for method in runs:
            self.assertEqual(repeat[method].selected_ids, runs[method].selected_ids)
            self.assertEqual(repeat[method].memory.trace, runs[method].memory.trace)

    def test_zero_budget_matches_b2_and_empty_history_is_supported(self):
        expected = run_baseline(self.events, self.complete, entity="p", method="B2")
        for run in self.run_pair(0).values():
            self.assertEqual(run.memory.trace, expected.trace)
            self.assertEqual((run.selected_ids, run.attempts), ((), 0))
        for run in self.run_pair(0, events=[]).values():
            self.assertEqual(run.memory.trace, ())
        self.assertEqual(self.invoked, [])

    def test_failed_attempts_preserve_state_and_count_in_both_methods(self):
        def fail(claim, target):
            if claim.value == "Dogwood":
                return "malformed"
            raise TimeoutError

        for run in self.run_pair(3, verify=fail).values():
            self.assertEqual((run.attempts, run.failures, run.stale_targets), (3, 3, 0))
            current, = run.memory.retrieve("p", "job", as_of=date(2026, 3, 4))
            self.assertEqual(current.value, "Alder")

    def test_infeasible_target_or_unordered_input_fails_before_verification(self):
        for calls in (-1, True, 4):
            with self.subTest(calls=calls), self.assertRaises(ValueError):
                self.run_pair(calls)
        with self.assertRaisesRegex(ValueError, "chronological"):
            self.run_pair(1, events=reversed(self.events))
        self.assertEqual(self.invoked, [])
