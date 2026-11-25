"""Development-only retrieval comparators with shared reader evidence limits."""

from datetime import date
import json
import re

from trace_mem.memory import Fact, Source
from trace_mem.semantic import _cosine, _unit_embeddings


EDIT = re.compile(r"\b(?:please (?:remove|forget|delete)|no longer (?:need|track)|"
                  r"i need to (?:remove|delete)|you can remove)\b", re.I)


def in_scope(event, cutoff, spec):
    source = f"{event.session_id}/{event.turn}"
    return (event.role == "user" and event.observed_on <= cutoff and event.message.strip()
            and event.session_id not in spec["excluded_sessions"]
            and source not in spec["excluded_turns"] and not EDIT.search(event.message))


def candidate_event(event, entity):
    identifier = f"{event.session_id}/{event.turn}"
    return Fact(identifier, entity, "source excerpt", event.message,
                Source(event.observed_on, identifier), event.observed_on)


def ranked_sources(question, events, spec, embed, entity):
    rows = [candidate_event(e, entity) for e in events if in_scope(e, question.as_of, spec)]
    if not rows:
        return ()
    query, *encoded = _unit_embeddings(embed, (question.text, *(row.value for row in rows)))
    ordered = sorted(zip(rows, encoded), key=lambda pair: (-_cosine(query, pair[1]), pair[0].fact_id))
    return tuple(row for row, _ in ordered[:spec["k"]])


def trim(question, facts, budget, k):
    """Freeze one conservative UTF-8 envelope inside the common 4,096-token context."""
    remaining = max(0, budget - len(json.dumps(question.text).encode()))
    retained = []
    for fact in facts:
        size = len(json.dumps((fact.fact_id, fact.predicate, fact.value)).encode())
        if size <= remaining:
            retained.append(fact)
            remaining -= size
        if len(retained) == k:
            break
    return tuple(retained)


def evidence_metrics(nominated, emitted, active, retrieved):
    references = set(nominated)
    return {"nominated_source_turns": len(references),
            "extracted_turns": len(references.intersection(emitted)),
            "represented_turns": len(references.intersection(active)),
            "retrieved_turns": len(references.intersection(f.source.reference for f in retrieved))}
