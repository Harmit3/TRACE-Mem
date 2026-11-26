from datetime import date
import json

import pytest

from scripts.audit_step33 import rejection
from scripts.run_step33 import match
from trace_mem.data.memora import Event
from trace_mem.extractor_v3 import eligible_user_fields, extract, parse, segments
from trace_mem.llm_tasks import MockProvider
from trace_mem.memory import Fact, Source
from trace_mem.reader_v3 import read


DAY = date(2026, 3, 1)


def test_segmentation_preserves_unicode_byte_ceiling_and_offsets():
    message = "随" * 2100
    windows = list(segments(message))
    assert windows[0][0] == 0
    assert all(message[start:start + len(text)] == text and len(text.encode()) <= 1450
               for start, text in windows)
    assert windows[-1][0] + len(windows[-1][1]) == len(message)
    assert all(second <= first + len(text) for (first, text), (second, _) in zip(windows, windows[1:]))


def test_assistant_claim_is_attributed_and_never_projection_eligible():
    event = Event(DAY, 2, 4, "assistant", "The venue is Harbor Hall.")
    proposal = '[{"category":"location","value":"Harbor Hall","evidence":"The venue is Harbor Hall.","intent":"assert"}]'
    result = extract(MockProvider(lambda *_: proposal), event)
    assert result.findings[0].source == "2/4"
    assert result.findings[0].trust == "assistant-attributed"
    assert eligible_user_fields(result) == ()
    with pytest.raises(ValueError):
        parse(proposal.replace("Harbor", "Fictional"), event.message, event, 0)


def test_restriction_fails_closed_even_after_successful_empty_extraction():
    event = Event(DAY, 1, 1, "user", "Please forget my venue. I like apples.")
    result = extract(MockProvider(lambda *_: "[]"), event)
    assert result.failed == 0 and result.quarantine
    assert eligible_user_fields(result) == ()
    malformed = extract(MockProvider(lambda *_: "{}"), event)
    assert malformed.failed == 1 and malformed.quarantine


def test_reader_retries_unknown_id_then_composes_only_supplied_text():
    fact = Fact("f", "p", "venue", "The venue is not Harbor Hall.", Source(DAY, "1/2"), DAY)
    responses = iter(('{"status":"supported","ids":["wrong"]}', '{"status":"supported","ids":["f"]}'))
    answer = read(MockProvider(lambda *_: next(responses)), "Was Harbor Hall chosen?", (fact,),
                  as_of=DAY, mode="short").answer
    assert answer.citations == ("f",)
    assert answer.text == fact.value


def test_failure_diagnostics_and_validation_matching():
    assert rejection({"done_reason": "length"}, DAY) == "terminal-length"
    assert rejection({"done_reason": "stop", "message": {"content": "not JSON"}}, DAY) == "malformed-json"
    assert match([("13 steps", "assert")], [("3 steps", "assert")]) == 0
