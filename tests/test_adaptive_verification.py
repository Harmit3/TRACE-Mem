"""Regression checks for causality, pacing, and backwards compatibility."""

from datetime import date
from types import SimpleNamespace

from trace_mem.adaptive_verification import AdaptiveAllocation, heuristic_score, neutralized_score
from trace_mem.baselines import PreparedClaim
from trace_mem.claims import Claim
from trace_mem.controller import LogisticController
from trace_mem.data.memora import Event
from trace_mem.memora_benchmark import run_suite
from trace_mem.memory import Source


def test_pacing_responds_to_remaining_capacity_without_future_scores():
    p = AdaptiveAllocation(sum, (0.1, 0.2, 0.4, 0.8), 4)
    assert not p.choose(0.2, remaining=1, seen=1)
    assert p.choose(0.4, remaining=1, seen=1)
    assert p.choose(0.0, remaining=1, seen=4)
    assert p.choose(0.0, remaining=4, seen=1)
    assert not p.choose(0.9, remaining=0, seen=4)


def test_budget_neutralization_removes_only_frozen_budget_coordinate():
    model = SimpleNamespace(controller=LogisticController((0,) * 8, (1,) * 8,
                                                            (1, 0, 0, 0, 0, 0, 0, -1), 0))
    x = (0.7, 0, 1, 0, 30, 0.5, 0.5, 1)
    depleted = (*x[:-1], 0)
    assert model.controller.score(x) < model.controller.score(depleted)
    assert neutralized_score(model, x) == neutralized_score(model, depleted)
    assert heuristic_score(x) > heuristic_score((*x[:6], 1, x[7]))


def test_extra_policy_does_not_change_t1_and_observes_hard_cap():
    days = [date(2025, 1, n) for n in (1, 2, 3)]
    messages = ("My job is Cedar.", "I now work at Ash.", "I now work at Birch.")
    events = tuple(Event(day, i, 1, "user", text)
                   for i, (day, text) in enumerate(zip(days, messages), 1))
    items = tuple(PreparedClaim(Claim("job", value, "assert", day), Source(day, f"{i}/1"), f"{i}/1/0")
                  for i, (day, value) in enumerate(zip(days, ("Cedar", "Ash", "Birch")), 1))
    model = SimpleNamespace(controller=LogisticController((0,) * 8, (1,) * 8, (0,) * 8, -1),
                            threshold=0.8)
    tasks = SimpleNamespace(verify=lambda *args, **kwargs: "update")
    features = lambda *args, **kwargs: (0.1, 0.5, 1, 0, 2, 0, 0.5, kwargs["budget_remaining_fraction"])
    kwargs = dict(entity="persona", tasks=tasks, models={"T1": model, "T1-no-NLI": model},
                  builders=dict.fromkeys(("T1", "T1-no-NLI", "T2"), features), cap=1, seed=23)
    p = AdaptiveAllocation(lambda _: 0.9, (0.9,), 2)
    original = run_suite(events, items, mode="closed-loop", **kwargs)
    extended = run_suite(events, items, mode="closed-loop", adaptive={"T2": p}, **kwargs)
    assert original["T1"][1] == extended["T1"][1]
    assert extended["T2"][1]["verification_attempts"] == 1
    fixed = run_suite(events, items, mode="fixed", adaptive={"T2": p}, **kwargs)
    assert fixed["T2"][1]["verification_attempts"] == fixed["B4"][1]["verification_attempts"] == 1
