from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest

from trace_mem.adaptive_verification import AdaptiveAllocation
from trace_mem.baselines import PreparedClaim
from trace_mem.causal_horizon_v1 import CalendarPlanner
from trace_mem.claims import Claim
from trace_mem.fixture_independence_v1 import mechanism_hash, normalized_text, overlap
from trace_mem.llm_tasks import Answer
from trace_mem.memory import Source
from trace_mem.validation_v2 import (Check, Episode, ExactLedger, Gold, evaluate, failed_condition,
                                     paired, replay, run_reviewed, summarize_primary,
                                     reader_outcome, reader_evidence)


START = date(2025, 1, 1)
END = START + timedelta(days=6)
POLICIES = ("B3", "T2", "H-paced", "T2-no-NLI")


def small_episode():
    d = START + timedelta(days=1)
    days = (START, d, d + timedelta(days=1))
    items = tuple(PreparedClaim(Claim("slot", value, "correct" if i else "assert", day),
                                Source(day, f"source-{i}"), f"f{i}")
                  for i, (value, day) in enumerate(zip(("old", "next", "final"), days, strict=True)))
    return Episode("engineering", "engineering", START, END, items,
                   frozenset(x.fact_id for x in items), ("restricted-example",))


class ValidationTests(unittest.TestCase):
    def test_causal_prior_and_pacing(self):
        planner = CalendarPlanner(START, END)
        rule = AdaptiveAllocation(lambda x: x[0], (0.2, 0.7), 10)
        self.assertEqual(planner.future(START, 0), 10)
        self.assertEqual(planner.future(END, 100), 0)
        self.assertEqual(planner.future(START, 100), 20)
        self.assertFalse(planner.choose(rule, 1, day=START, previous=0, remaining=0))
        self.assertTrue(planner.choose(rule, 0, day=END, previous=0, remaining=1))
        self.assertEqual(rule.planned_candidates, 10)

    def test_equal_caps_cache_token_accounting_and_non_gold_replay(self):
        episode = small_episode()
        deliveries = []
        def provider(claim, old, evidence):
            self.assertEqual(evidence, "")
            deliveries.append((claim.value, old.value))
            return "update", 30, 8
        with tempfile.TemporaryDirectory() as d:
            ledger = ExactLedger(Path(d) / "test.sqlite", "engineering")
            first = replay(episode, "B3", 2, "closed-loop", {}, None, provider, ledger)
            second = replay(episode, "B3", 2, "closed-loop", {}, None, provider, ledger)
            zero = replay(episode, "B3", 0, "closed-loop", {}, None, provider, ledger)
            self.assertEqual(len(deliveries), 2)
            self.assertEqual(first[1]["fresh_requests"], 2)
            self.assertEqual(second[1]["fresh_requests"], 0)
            self.assertEqual(first[1]["logical_input_tokens"], second[1]["logical_input_tokens"])
            self.assertEqual(zero[1]["calls"], 0)
            self.assertEqual(first[4][1]["future_observed"], 1)
            self.assertNotIn("gold", first[4][1])

    def test_unresolved_scope_blocks_future_verification_and_reader(self):
        e = small_episode()
        d = e.events[0].source.observed_on
        request = PreparedClaim(Claim("unknown", "other", "delete", d), Source(d, "early"), "delete")
        e = Episode(e.identity, e.family, e.opening, e.closing, (request, *e.events), e.permitted, e.restricted_values)
        with tempfile.TemporaryDirectory() as tmp:
            result = replay(e, "B3", 5, "fixed", {}, None, lambda *_: self.fail("Verifier leaked"),
                            ExactLedger(Path(tmp) / "ledger.sqlite", "engineering"))
        self.assertTrue(result[2])
        self.assertEqual(result[1]["calls"], 0)

    def test_reader_absence_keeps_full_denominator(self):
        e = small_episode()
        with tempfile.TemporaryDirectory() as d:
            state = replay(e, "B3", 0, "closed-loop", {}, None, None,
                           ExactLedger(Path(d) / "test.sqlite", "engineering"))[0]
            index = reader_evidence(state, e)
            gold = Gold((), False, (), frozenset())
            self.assertEqual(reader_outcome(lambda *_: None, index, e, gold, "q"), ("missing", 0))
            self.assertEqual(reader_outcome(lambda *_: Answer(None, ()), index, e, gold, "q"),
                             ("abstained", 1))
            self.assertEqual(reader_outcome(lambda *_: Answer("guess", ("outside",)), index, e, gold, "q"),
                             ("authorization-failure", 0))
        self.assertEqual(failed_condition()["reader_total"], 1)

    def test_daily_snapshots_do_not_use_retroactive_future_update(self):
        episode = small_episode()
        later = episode.events[2]
        retroactive = PreparedClaim(Claim("slot", "final", "correct", START + timedelta(days=1)),
                                    later.source, later.fact_id)
        episode = Episode(episode.identity, episode.family, START, END,
                          (episode.events[0], retroactive), episode.permitted - {"f1"},
                          episode.restricted_values)
        checks = tuple(Check(START + timedelta(days=i), START + timedelta(days=i), "slot",
                             ("old",) if i == 1 else ("final",), "current")
                       for i in (1, 2, 3, 4, 5, 6))
        checks += tuple(Check(START + timedelta(days=i), START, "slot", ("old",), "historical")
                        for i in range(1, 6))
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ExactLedger(Path(tmp) / "ledger.sqlite", "engineering")
            scores = evaluate(episode, Gold(checks, False, (), frozenset()), "q", "B3", 0,
                              "closed-loop", {}, None, None, ledger, lambda *_: None)
        self.assertEqual(scores["current"], 6)
        self.assertEqual(scores["historical"], 5)

    def test_family_weighting_and_adjusted_bootstrap(self):
        self.assertEqual(paired(((.25, .25), (-.5, -.5))), ((.25, .25, .25), (-.5, -.5, -.5)))
        data = []
        for family, t2 in (("a", 6), ("b", 0)):
            for p in POLICIES:
                data.append(dict(family=family, history=family, policy=p, cap=2, mode="closed-loop",
                                 current=t2 if p == "T2" else 0, current_total=6))
        self.assertEqual(summarize_primary(data)[0], (.5, 0.0, 1.0))
        with self.assertRaisesRegex(ValueError, "Missing planned"):
            summarize_primary(data[:-1])

    def test_structural_renaming_cannot_make_a_new_mechanism(self):
        a = mechanism_hash([("Alice", "work", "town", "replace", "current", "direct", ())])
        b = mechanism_hash([("Iris", "project", "place", "replace", "current", "direct", ())])
        self.assertEqual(a, b)
        x = normalized_text("Alice near 12", {"Alice": "entity"})
        y = normalized_text("Iris near 23", {"Iris": "entity"})
        self.assertEqual(x, y)
        self.assertEqual(overlap(x, a, [("prior", y, b)]), [("prior", 1, True)])

    def test_pending_cohort_produces_no_output(self):
        path = Path("results/step36-refused-engineering")
        with self.assertRaisesRegex(ValueError, "90 reviewed families"):
            run_reviewed([], {}, path, rules={}, feature=None, provider=None, reader=None)
        self.assertFalse(path.exists())
