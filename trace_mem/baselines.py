"""Run memory and verification policies over the same extracted claims."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import math
from typing import Literal

from trace_mem.claims import Claim, conflicts, extract
from trace_mem.controller import FEATURE_NAMES, LogisticController, features_for
from trace_mem.data.memora import Event
from trace_mem.memory import Fact, Source, TemporalMemory
from trace_mem.semantic import SemanticEvidence
from trace_mem.verification import Budget, Verdict, select_random, select_ranked


VerificationGate = Callable[[Claim, Fact, Budget], bool]
Verifier = Callable[[Claim, Fact], Verdict]


@dataclass(frozen=True, slots=True)
class PreparedClaim:
    claim: Claim
    source: Source
    fact_id: str


@dataclass(frozen=True, slots=True)
class VerificationRun:
    memory: TemporalMemory
    selected_ids: tuple[str, ...]
    attempts: int
    failures: int
    stale_targets: int


def _prepare(events: Iterable[Event], complete: Callable[[str, str], str]) -> Iterable[PreparedClaim]:
    previous = None
    for event in events:
        key = event.observed_on, event.session_id, event.turn
        if previous is not None and key <= previous:
            raise ValueError("Events must be in strict chronological order")
        previous = key
        source = Source(event.observed_on, f"{event.session_id}/{event.turn}")
        for ordinal, claim in enumerate(extract(event, complete)):
            yield PreparedClaim(claim, source, f"{source.reference}/{ordinal}")


def _eligible_target(memory: TemporalMemory, entity: str, claim: Claim) -> Fact | None:
    if claim.intent == "delete":
        return None
    competing = conflicts(memory, entity, claim)
    if len(competing) == 1 and competing[0].valid_from < claim.effective_on:
        return competing[0]
    return None


def run_matched_baselines(
    events: Iterable[Event],
    complete: Callable[[str, str], str],
    *,
    entity: str,
    calls: int,
    seed: int,
    verify: Verifier,
    controller: LogisticController | None = None,
    semantic: SemanticEvidence | None = None,
) -> dict[str, VerificationRun]:
    """Replay B4, B5 and optional T1 on frozen B2 evidence at exactly the same cost in calls."""
    if type(calls) is not int or calls < 0:
        raise ValueError("Expected a nonnegative integer call target")
    if type(seed) is not int:
        raise ValueError("Expected an integer seed")
    if controller is not None:
        _validate_controller(controller)
    elif semantic is not None:
        raise ValueError("Semantic policy evidence requires a T1 controller")
    prepared = tuple(_prepare(events, complete))
    reference = TemporalMemory()
    candidates: list[tuple[PreparedClaim, Fact]] = []
    for item in prepared:
        target = _eligible_target(reference, entity, item.claim)
        if target is not None:
            candidates.append((item, target))
        _apply(reference, entity, item.claim, item.source, item.fact_id, "B2", None, None, None)

    # Uncertain statements outrank implicit changes and explicit corrections.
    priority = {"uncertain": 2, "assert": 1, "correct": 0}
    selections = {
        "B4": select_random(len(candidates), calls, seed=seed),
        "B5": select_ranked([priority[item.claim.intent] for item, _ in candidates], calls),
    }
    if controller is not None:
        scores = [
            controller.score(features_for(item.claim, target, entity=entity, source=item.source,
                                          budget_remaining_fraction=1.0,
                                          semantic=semantic))
            for item, target in candidates
        ] if calls else []
        selections["T1"] = select_ranked(scores, calls)
    runs = {}
    for method, selected in selections.items():
        targets = {item.fact_id: target for index, (item, target) in enumerate(candidates)
                   if index in selected}
        memory = TemporalMemory()
        budget = Budget(calls)
        stale_targets = 0
        for item in prepared:
            claim, source, fact_id = item.claim, item.source, item.fact_id
            target = targets.get(fact_id)
            if target is not None:
                live = _eligible_target(memory, entity, claim)
                verdict = budget.call(verify, claim, target)
                if live is None or live.fact_id != target.fact_id:
                    stale_targets += 1
                else:
                    _apply_verdict(memory, entity, item, live, verdict)
                    continue
            _apply(memory, entity, claim, source, fact_id, "B2", None, None, None)
        runs[method] = VerificationRun(memory, tuple(targets), budget.attempts,
                                       budget.failures, stale_targets)
    return runs


def _validate_controller(controller: LogisticController) -> None:
    if len(controller.weights) != len(FEATURE_NAMES):
        raise ValueError("T1 requires the eight README features")


def run_t1(
    events: Iterable[Event],
    complete: Callable[[str, str], str],
    *,
    entity: str,
    controller: LogisticController,
    threshold: float,
    calls: int,
    verify: Verifier,
    semantic: SemanticEvidence | None = None,
) -> VerificationRun:
    """Run a causal threshold policy under a hard cap, with possible underspend."""
    _validate_controller(controller)
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Threshold must be between zero and one")
    budget = Budget(calls)
    memory = TemporalMemory()
    selected_ids = []
    for item in _prepare(events, complete):
        claim, source, fact_id = item.claim, item.source, item.fact_id
        target = _eligible_target(memory, entity, claim) if budget.remaining else None
        if target is not None:
            features = features_for(claim, target, entity=entity, source=source,
                                    budget_remaining_fraction=budget.remaining / budget.limit,
                                    semantic=semantic)
            if controller.score(features) >= threshold:
                selected_ids.append(fact_id)
                _apply_verdict(memory, entity, item, target, budget.call(verify, claim, target))
                continue
        _apply(memory, entity, claim, source, fact_id, "B2", None, None, None)
    return VerificationRun(memory, tuple(selected_ids), budget.attempts, budget.failures, 0)


def run_baseline(
    events: Iterable[Event],
    complete: Callable[[str, str], str],
    *,
    entity: str,
    method: Literal["B1", "B2"],
    budget: Budget | None = None,
    should_verify: VerificationGate | None = None,
    verify: Verifier | None = None,
) -> TemporalMemory:
    if method not in ("B1", "B2"):
        raise ValueError("Expected B1 or B2")
    settings = (budget, should_verify, verify)
    if any(item is not None for item in settings) and (
        method != "B2" or any(item is None for item in settings)
    ):
        raise ValueError("Selective replay requires B2, a budget, a gate and a verifier")
    memory = TemporalMemory()
    for item in _prepare(events, complete):
        _apply(memory, entity, item.claim, item.source, item.fact_id, method,
               budget, should_verify, verify)
    return memory


def _apply_verdict(
    memory: TemporalMemory, entity: str, item: PreparedClaim, target: Fact, verdict: Verdict,
) -> None:
    if verdict == "update":
        claim = item.claim
        fact = Fact(item.fact_id, entity, claim.predicate, claim.value, item.source,
                    claim.effective_on, claim.expires_on)
        memory.accept(fact, replaces=target.fact_id)
    else:
        memory.defer(item.fact_id, item.source)


def _apply(
    memory: TemporalMemory, entity: str, claim: Claim, source: Source,
    fact_id: str, method: Literal["B1", "B2"],
    budget: Budget | None, should_verify: VerificationGate | None, verify: Verifier | None,
) -> None:
    same = memory.matching_ids(entity, claim.predicate, claim.value)
    if claim.intent == "delete":
        for target in same:
            memory.delete(target, source)
        if not same:
            memory.defer(fact_id, source)
        return
    fact = Fact(fact_id, entity, claim.predicate, claim.value, source,
                claim.effective_on, claim.expires_on)
    competing = conflicts(memory, entity, claim) if method == "B2" else ()
    target = competing[0] if len(competing) == 1 else None
    if (target is not None and claim.effective_on > target.valid_from
            and budget is not None and should_verify is not None and verify is not None
            and budget.remaining and should_verify(claim, target, budget)):
        _apply_verdict(memory, entity, PreparedClaim(claim, source, fact_id), target,
                       budget.call(verify, claim, target))
        return
    if claim.intent == "uncertain":
        memory.defer(fact_id, source)
        return
    if competing:
        if claim.intent != "correct" or target is None or claim.effective_on <= target.valid_from:
            memory.defer(fact_id, source)
        else:
            memory.accept(fact, replaces=target.fact_id)
    else:
        memory.accept(fact)
