"""Run append-only and temporal-rule baselines over the same extracted claims."""

from collections.abc import Callable, Iterable
from typing import Literal

from trace_mem.claims import Claim, conflicts, extract
from trace_mem.data.memora import Event
from trace_mem.memory import Fact, Source, TemporalMemory


def run_baseline(
    events: Iterable[Event],
    complete: Callable[[str, str], str],
    *,
    entity: str,
    method: Literal["B1", "B2"],
) -> TemporalMemory:
    if method not in ("B1", "B2"):
        raise ValueError("Expected B1 or B2")
    memory = TemporalMemory()
    for event in events:
        source = Source(event.observed_on, f"{event.session_id}/{event.turn}")
        for ordinal, claim in enumerate(extract(event, complete)):
            _apply(memory, entity, claim, source, f"{source.reference}/{ordinal}", method)
    return memory


def _apply(
    memory: TemporalMemory, entity: str, claim: Claim, source: Source,
    fact_id: str, method: Literal["B1", "B2"],
) -> None:
    same = memory.matching_ids(entity, claim.predicate, claim.value)
    if claim.intent == "delete":
        for target in same:
            memory.delete(target, source)
        if not same:
            memory.defer(fact_id, source)
        return
    if claim.intent == "uncertain":
        memory.defer(fact_id, source)
        return

    fact = Fact(fact_id, entity, claim.predicate, claim.value, source,
                claim.effective_on, claim.expires_on)
    competing = conflicts(memory, entity, claim) if method == "B2" else ()
    if competing:
        if (claim.intent != "correct" or len(competing) != 1
                or claim.effective_on <= competing[0].valid_from):
            memory.defer(fact_id, source)
        else:
            memory.accept(fact, replaces=competing[0].fact_id)
    else:
        memory.accept(fact)
