"""Rebuilt, allowlisted evidence index for local development evaluation."""

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json

from trace_mem.memory import Fact, Source
from trace_mem.semantic import _cosine, _unit_embeddings


@dataclass(frozen=True)
class Field:
    identity: str
    source: str
    text: str
    predicate: str
    observed: date
    start: date
    end: date | None = None
    parents: tuple[str, ...] = ()


@dataclass(frozen=True)
class Handle:
    namespace: str
    cutoff: date
    identities: tuple[str, ...]


class EvidenceIndexV2:
    """Only sanitized fields are indexed; alternate views share one instance."""

    def __init__(self, fields, grant_fingerprint):
        self._generation = 0
        self._fields = {}
        self.rebuild(fields, grant_fingerprint)

    def rebuild(self, fields, grant_fingerprint):
        fields = tuple(fields)
        verified = {}
        for field in fields:
            if (field.identity in verified or not field.text.strip()
                    or (field.end is not None and field.end <= field.start)
                    or any(p not in verified for p in field.parents)):
                raise ValueError("Invalid field, interval, or derivative lineage")
            if field.parents and field.text != "\n".join(verified[p].text for p in field.parents):
                raise ValueError("Derived evidence must be a verbatim composition of approved parents")
            verified[field.identity] = field
        self._generation += 1
        self._fields = verified
        fingerprint = [(f.identity, f.source, f.predicate, f.text, f.observed.isoformat(),
                        f.start.isoformat(), f.end.isoformat() if f.end else None, f.parents)
                       for f in fields]
        self.namespace = sha256(json.dumps(
            [grant_fingerprint, self._generation, fingerprint], sort_keys=True).encode()).hexdigest()

    def _visible(self, field, cutoff, identity, seen):
        if identity in seen:
            return True
        seen.add(identity)
        return (field.observed <= cutoff and field.start <= cutoff
                and (field.end is None or cutoff < field.end)
                and all(self._visible(self._fields[p], cutoff, p, seen) for p in field.parents))

    def retrieve(self, text, cutoff, embed, *, k, view=None):
        if type(k) is not int or k < 0:
            raise ValueError("Expected a nonnegative retrieval limit")
        pool = self._fields if view is None else view
        identities = [i for i in dict.fromkeys(pool) if i in self._fields
                      and self._visible(self._fields[i], cutoff, i, set())]
        if not k or not identities:
            return Handle(self.namespace, cutoff, ())
        query, *vectors = _unit_embeddings(embed, (text, *(self._fields[i].text for i in identities)))
        ranked = sorted(zip(identities, vectors), key=lambda item: (-_cosine(query, item[1]), item[0]))
        return Handle(self.namespace, cutoff, tuple(i for i, _ in ranked[:k]))

    def materialize(self, handle, entity):
        if handle.namespace != self.namespace:
            return ()
        output = []
        for identity in handle.identities:
            field = self._fields.get(identity)
            if field is None or not self._visible(field, handle.cutoff, identity, set()):
                continue
            output.append(Fact(f"v2-{self.namespace[:12]}-{identity}", entity, field.predicate, field.text,
                               Source(field.observed, field.source), field.start, field.end))
        return tuple(output)
