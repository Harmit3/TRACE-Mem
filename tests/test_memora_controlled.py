"""Check source grounding and deterministic temporal expectations for Step 22."""

from datetime import date
import json

import pytest

from scripts.run_memora_controlled import DESIGN, assess, bound_sessions, source_claim, synthetic_input
from trace_mem.data.memora import Event
from trace_mem.memory import TemporalMemory


def test_oracle_rejects_unquoted_and_assistant_values():
    day = date(2025, 1, 1)
    user = Event(day, 2, 1, "user", "I live at Pine Lane.")
    assert source_claim(user, "residence", "Pine Lane", "assert").source.reference == "2/1"
    for e, value in ((user, "Willow Lane"), (Event(day, 2, 2, "assistant", user.message), "Pine Lane")):
        with pytest.raises(ValueError, match="verbatim"):
            source_claim(e, "residence", value, "assert")


def test_session_boundary_and_independent_fictional_checks():
    config = json.loads(DESIGN.read_bytes())
    for fixture in config["synthetic"]:
        events, prepared, checks, (question,), answer = synthetic_input(fixture)
        assert len(bound_sessions(events, 2)) == 2
        assert len(prepared) == len(events) == 10
        assert all(any(c.claim.value in e.message and c.source.reference == f"{e.session_id}/{e.turn}"
                       for e in events) for c in prepared)
        assert answer and question.observed_on == events[-1].observed_on
        empty = assess(TemporalMemory(), "person", question.observed_on, checks, prepared)
        assert empty["checks"] == {"historical": {"total": 4, "correct": 0},
                                   "current": {"total": 8, "correct": 4},
                                   "deletion": {"total": 2, "correct": 2}}
