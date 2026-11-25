"""Tests for contextual provenance isolation, strict extraction and local judging."""

from datetime import date
import json

import pytest

from scripts.validate_memora_quality import key, metrics
from trace_mem.context_extraction import contextual_prepare, extract_event, strict_claims
from trace_mem.data.memora import Event
from trace_mem.llm_tasks import LLMTasks, MockProvider
from trace_mem.local_rubric import judge


def test_context_is_recent_user_only_and_resets_at_session_boundary():
    day = date(2025, 1, 1)
    payloads = []

    def response(task, payload):
        assert task == "extract-v1"
        payloads.append(json.loads(payload))
        return "[]"

    tasks = LLMTasks(MockProvider(response))
    events = tuple(Event(day, session, turn, role, text) for session, turn, role, text in (
        (1, 1, "user", "first"),
        (1, 2, "assistant", "ignore assistant assertions"),
        (1, 3, "user", "second"),
        (2, 1, "user", "new session"),
    ))
    assert contextual_prepare(events, tasks) == ((), {})
    assert [row["prior_user_turns"] for row in payloads] == [[], ["first"], []]
    assert all(set(row) == {"observed_on", "message", "prior_user_turns"} for row in payloads)
    extract_event(tasks, events[0], ("x" * 5000,), improved=True)
    assert not payloads[-1]["prior_user_turns"]


def test_strict_claims_reject_extra_fields_and_duplicates():
    day = date(2025, 1, 1)
    claim = {"predicate": "job", "value": "Elm Press", "intent": "assert"}
    for rows in ([claim, claim], [claim | {"gold": "unexpected"}], [claim] * 13):
        with pytest.raises(ValueError):
            strict_claims(json.dumps(rows), day)
    assert strict_claims(json.dumps([claim]), day)[0].value == "Elm Press"


def test_judge_input_excludes_expected_label_and_rejects_invalid_output():
    def valid(task, payload):
        assert task == "local-rubric-v1"
        assert json.loads(payload) == {"answer": None, "check": "Does it mention Elm Press?"}
        return '{"judgment":"no"}'

    assert judge(MockProvider(valid), None, "Does it mention Elm Press?") == "no"
    with pytest.raises(ValueError):
        judge(MockProvider(lambda *_: '{"judgment":"maybe"}'), None, "Check")


def test_metrics_count_wrong_intent_separately_from_deletion():
    delete = key("job", "Elm Press", "delete")
    asserted = key("job", "Elm Press", "assert")
    result = metrics([({asserted}, {delete}), ({delete}, {delete})])
    assert result["precision"] == result["recall"] == result["f1"] == 0.5
    assert result["matched_deletions"] == 1
    assert result["unmatched_predictions"] == 1
