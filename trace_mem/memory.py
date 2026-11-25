"""Deterministic fact transitions and effective-time retrieval for one history."""

from dataclasses import dataclass, replace
from datetime import date
from typing import Literal


@dataclass(frozen=True, slots=True)
class Source:
    observed_on: date
    reference: str


@dataclass(frozen=True, slots=True)
class Fact:
    fact_id: str
    entity: str
    predicate: str
    value: str
    source: Source
    valid_from: date
    valid_to: date | None = None
    supersedes: str | None = None

    def visible_on(self, day: date) -> bool:
        return self.valid_from <= day and (self.valid_to is None or day < self.valid_to)


@dataclass(frozen=True, slots=True)
class Transition:
    operation: Literal["add", "supersede", "defer", "delete"]
    source: Source
    fact_id: str
    target_id: str | None = None


class TemporalMemory:
    """Store facts with opaque IDs and payload-free transitions.

    Callers supply resolved operations. Ambiguous candidates should be deferred.
    One instance represents one replay history. References must be opaque IDs.
    """

    def __init__(self) -> None:
        self._facts: dict[str, Fact] = {}
        self._deleted: set[str] = set()
        self._trace: list[Transition] = []

    @property
    def trace(self) -> tuple[Transition, ...]:
        return tuple(self._trace)

    def _check_source(self, source: Source) -> None:
        if not source.reference:
            raise ValueError("Source reference is required")
        if self._trace and source.observed_on < self._trace[-1].source.observed_on:
            raise ValueError("Transitions must follow observation order")

    def accept(self, fact: Fact, *, replaces: str | None = None) -> None:
        self._check_source(fact.source)
        if not all((fact.fact_id, fact.entity, fact.predicate, fact.value)):
            raise ValueError("Fact identity and value are required")
        if fact.fact_id in self._facts or fact.fact_id in self._deleted:
            raise ValueError("Fact ID has already been used")
        if fact.supersedes is not None:
            raise ValueError("Use replaces to establish revision provenance")
        if fact.valid_to is not None and fact.valid_to <= fact.valid_from:
            raise ValueError("End date must follow start date")
        if replaces is not None:
            old = self._facts.get(replaces)
            if old is None or (old.entity, old.predicate) != (fact.entity, fact.predicate):
                raise ValueError("Replacement requires an existing fact for the same entity and predicate")
            if fact.valid_from <= old.valid_from or not old.visible_on(fact.valid_from):
                raise ValueError("Replacement date must fall after the start of the target interval")
            self._facts[replaces] = replace(old, valid_to=fact.valid_from)
            fact = replace(fact, supersedes=replaces)
        self._facts[fact.fact_id] = fact
        operation = "supersede" if replaces is not None else "add"
        self._trace.append(Transition(operation, fact.source, fact.fact_id, replaces))

    def defer(self, fact_id: str, source: Source) -> None:
        self._check_source(source)
        self._trace.append(Transition("defer", source, fact_id))

    def delete(self, fact_id: str, source: Source) -> None:
        self._check_source(source)
        self._facts.pop(fact_id, None)
        self._deleted.add(fact_id)
        self._trace.append(Transition("delete", source, fact_id))

    def retrieve(self, entity: str, predicate: str | None, *, as_of: date) -> tuple[Fact, ...]:
        """Find facts valid at as_of using the latest replayed privacy state."""
        matches = (
            fact for fact in self._facts.values()
            if fact.entity == entity and (predicate is None or fact.predicate == predicate)
            and fact.visible_on(as_of)
        )
        return tuple(sorted(matches, key=lambda fact: (fact.valid_from, fact.fact_id), reverse=True))

    def matching_ids(self, entity: str, predicate: str, value: str) -> tuple[str, ...]:
        """Resolve exact deletion targets across all effective dates."""
        return tuple(fact.fact_id for fact in self._facts.values()
                     if (fact.entity, fact.predicate, fact.value.casefold())
                     == (entity, predicate, value.casefold()))
