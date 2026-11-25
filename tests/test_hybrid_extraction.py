"""Exercise the experimental source and privacy boundary with deterministic providers."""

from datetime import date
import json

import pytest

from trace_mem.data.memora import Event
from trace_mem.hybrid_extraction import HybridReplay, TASK, normalize
from trace_mem.llm_tasks import MockProvider


DAY = date(2025, 1, 2)


def event(turn, text):
    return Event(DAY, 1, turn, "user", text)


def row(value, *, intent="assert", target=-1, evidence=0):
    return {"predicate": "job", "value": value, "intent": intent, "evidence": evidence,
            "target": target, "effective_on": None}


def test_unsupported_value_reference_and_date_are_rejected():
    observed = event(1, "I work at Cedar Mills.")
    for item in (row("Invented"), row("Cedar Mills", evidence=17),
                 row("Cedar Mills") | {"effective_on": "2001-01-01"}):
        with pytest.raises(ValueError):
            normalize(MockProvider(lambda *_: json.dumps([item])), observed)


def test_resolved_deletion_purges_quotes_history_and_blocks_exact_readdition():
    seen = []

    def response(task, payload):
        assert task == TASK
        data = json.loads(payload)
        seen.append(data)
        quote = data["evidence"]["0"]
        if "no longer" in quote:
            assert data["known_memory"] == [{"id": 0, "predicate": "job", "value": "Cedar Mills"}]
            return json.dumps([row("Cedar Mills", intent="delete", target=0)])
        return json.dumps([row("Cedar Mills")])

    replay = HybridReplay("person", MockProvider(response))
    replay.ingest(event(1, "I work at Cedar Mills."))
    state = replay.state
    embeddings = lambda texts: [[1.0] for _ in texts]
    assert state.evidence("job", DAY, 1, embeddings) == (("1/1/0", "I work at Cedar Mills."),)
    replay.ingest(event(2, "You no longer need to remember my employer."))
    replay.ingest(event(3, "I work at Cedar Mills."))
    assert seen[-1]["context"] == seen[-1]["known_memory"] == []
    assert not state.evidence("Cedar Mills", DAY, 4, embeddings)
    assert not state.memory.retrieve("person", None, as_of=DAY)
    with pytest.raises(ValueError, match="ordered"):
        replay.ingest(event(2, "I work at Cedar Mills."))


def test_context_literal_is_retained_only_with_focal_evidence():
    claim, = normalize(MockProvider(lambda *_: json.dumps([row("Cedar Mills")])),
                       event(1, "That's where I work."), ("I chose Cedar Mills.",))
    assert claim.quote == "That's where I work."
    assert claim.context_quote == "I chose Cedar Mills."
