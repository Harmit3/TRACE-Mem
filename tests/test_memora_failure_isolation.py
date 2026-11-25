"""Check common evidence envelope, chronological exclusion and failure counters."""

from datetime import date

from scripts.run_memora_failure_isolation import response_snapshot
from trace_mem.data.memora import Event
from trace_mem.memora_benchmark import Question
from trace_mem.retrieval_diagnostic import candidate_event, evidence_metrics, ranked_sources, trim


DAY = date(2025, 1, 3)


def test_transcript_diagnostic_excludes_assistant_future_and_known_restrictions():
    events = (
        Event(DAY, 1, 1, "user", "Available evidence."),
        Event(DAY, 2, 1, "user", "Explicitly restricted."),
        Event(DAY, 3, 1, "assistant", "Assistant invented this."),
        Event(date(2025, 1, 4), 4, 1, "user", "Future evidence."),
        Event(DAY, 5, 1, "user", "Please delete the original location."),
    )
    question = Question("question", "remembering", "What happened?", DAY)
    spec = {"excluded_sessions": [], "excluded_turns": ["2/1"], "k": 8}
    found = ranked_sources(question, events, spec, lambda xs: [[1, 0] for _ in xs], "synthetic")
    assert [f.fact_id for f in found] == ["1/1"]
    assert trim(question, [candidate_event(events[0], "synthetic")], 1, 8) == ()


def test_scope_counts_use_source_locations_and_deduplicate():
    fact = candidate_event(Event(DAY, 1, 1, "user", "Available evidence."), "synthetic")
    counts = evidence_metrics(["1/1", "1/1", "2/1"], ["1/1", "2/1"], ["1/1"], (fact, fact))
    assert counts == {"nominated_source_turns": 2, "extracted_turns": 2,
                      "represented_turns": 1, "retrieved_turns": 1}


def test_terminal_snapshot_distinguishes_complete_json_from_token_limit():
    incomplete = response_snapshot({"done_reason": "length", "eval_count": 256,
                                    "message": {"content": '{"answer":'}})
    complete = response_snapshot({"done_reason": "stop", "eval_count": 21,
                                  "message": {"content": '{"answer":null,"citations":[]}'}})
    assert incomplete["output_tokens"] == 256 and not incomplete["json_object"]
    assert complete["keys_valid"] and complete["citations_are_list"]


def test_terminal_contract_captures_answer_type_without_response_text():
    from scripts.audit_reader_contract import contract_fields

    fields = contract_fields({"done_reason": "stop", "eval_count": 20,
                              "message": {"content": '{"answer":null,"citations":["focal"]}'}})
    assert fields["answer_kind"] == "null"
    assert fields["citation_count"] == 1
    assert "citations" not in fields
