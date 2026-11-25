"""Run append-only and temporal-rule baselines over the same extracted claims."""

from collections.abc import Callable, Iterable
from typing import Literal

from trace_mem.claims import Claim, conflicts, extract
from trace_mem.data.memora import Event
from trace_mem.memory import Fact, Source, TemporalMemory
from trace_mem.verification import Budget, Verdict


VerificationGate = Callable[[Claim, Fact, Budget], bool]
Verifier = Callable[[Claim, Fact], Verdict]


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
    for event in events:
        source = Source(event.observed_on, f"{event.session_id}/{event.turn}")
        for ordinal, claim in enumerate(extract(event, complete)):
            _apply(memory, entity, claim, source, f"{source.reference}/{ordinal}", method,
                   budget, should_verify, verify)
    return memory


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
        if budget.call(verify, claim, target) == "update":
            memory.accept(fact, replaces=target.fact_id)
        else:
            memory.defer(fact_id, source)
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
