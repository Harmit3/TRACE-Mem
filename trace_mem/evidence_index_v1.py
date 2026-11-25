"""Versioned evidence index with current authorization on every access."""

from dataclasses import dataclass
from datetime import date
from hashlib import sha256

from trace_mem.memory import Fact, Source
from trace_mem.semantic import _cosine, _unit_embeddings


@dataclass(frozen=True)
class EvidenceRecord:
    identifier: str
    text: str
    source: str
    observed_on: date
    effective_from: date
    scope: str
    parents: tuple[str, ...] = ()
    supersedes: str | None = None


@dataclass(frozen=True)
class EvidenceHandle:
    epoch: int
    identifiers: tuple[str, ...]
    cutoff: date


class EvidenceIndexV1:
    """One policy registry gates every ranking channel and historical lookup."""

    def __init__(self):
        self.records = {}
        self.restricted_sources = set()
        self.restricted_scopes = set()
        self.ended = {}
        self.epoch = 0
        self.quarantined = False

    def add(self, record):
        if (not record.identifier or not record.source or not record.scope or not record.text
                or record.identifier in self.records or any(p not in self.records for p in record.parents)):
            raise ValueError("Evidence requires unique identity and existing lineage")
        if record.supersedes is not None:
            prior = self.records.get(record.supersedes)
            if (prior is None or prior.scope != record.scope
                    or record.effective_from <= prior.effective_from):
                raise ValueError("Supersession must move an existing scope forward")
            self.ended.setdefault(prior.identifier, []).append((record.observed_on, record.effective_from))
        self.records[record.identifier] = record
        self.epoch += 1

    def revoke(self, *, source=None, scope=None):
        """Unknown scope disables both raw and structured evidence until review."""
        if source is None and scope is None:
            self.quarantined = True
        if source is not None:
            self.restricted_sources.add(source)
        if scope is not None:
            self.restricted_scopes.add(scope)
        self.epoch += 1

    def authorized(self, identifier):
        pending, visited = [identifier], set()
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            record = self.records[current]
            if (self.quarantined or record.source in self.restricted_sources
                    or record.scope in self.restricted_scopes):
                return False
            visited.add(current)
            pending.extend(record.parents)
        return True

    def authorized_end(self, identifier, cutoff):
        return min((end for observed, end in self.ended.get(identifier, ()) if observed <= cutoff),
                   default=date.max)

    def visible(self, identifier, cutoff):
        record = self.records[identifier]
        return (record.observed_on <= cutoff and record.effective_from <= cutoff
                < self.authorized_end(identifier, cutoff) and self.authorized(identifier))

    def retrieve(self, query, cutoff, embed, *, k, identifiers=None):
        pool = self.records if identifiers is None else identifiers
        eligible = [key for key in dict.fromkeys(pool) if self.visible(key, cutoff)]
        if not eligible:
            return EvidenceHandle(self.epoch, (), cutoff)
        query_vector, *vectors = _unit_embeddings(embed, (query, *(self.records[k].text for k in eligible)))
        ranked = sorted(zip(eligible, vectors), key=lambda part: (-_cosine(query_vector, part[1]), part[0]))
        return EvidenceHandle(self.epoch, tuple(key for key, _ in ranked[:k]), cutoff)

    def materialize(self, handle, entity):
        """A saved handle never confers authority after an index mutation."""
        if handle.epoch != self.epoch:
            return ()
        facts = []
        for key in handle.identifiers:
            if not self.visible(key, handle.cutoff):
                continue
            record = self.records[key]
            # Include the live scope identity and epoch in downstream request-cache keys.
            opaque = sha256(f"{record.source}/{record.scope}/{record.text}".encode()).hexdigest()[:12]
            facts.append(Fact(f"e1-{self.epoch}-{key}-{opaque}", entity, record.scope,
                              record.text, Source(record.observed_on, record.source), record.effective_from,
                              self.authorized_end(key, handle.cutoff)))
        return tuple(facts)
