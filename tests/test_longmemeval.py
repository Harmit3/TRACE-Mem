from collections import Counter

from scripts.longmemeval_blind import audit_prefix, bm25, managed_fields, transcript
from scripts.longmemeval_inputs import TYPES, choose, events, project
from scripts.longmemeval_score import evidence_labels, judge_prediction, recall
from trace_mem.memory import TemporalMemory


def fixture():
    return dict(question="Where?", question_type="knowledge-update", question_id="sample",
                answer="gold-only-reference", answer_session_ids=["answer_gold"],
                question_date="2023/05/03 (Wed) 12:00",
                haystack_dates=["2023/05/03 (Wed) 12:01", "2023/05/03 (Wed) 11:59",
                                "2023/05/01 (Mon) 12:00"],
                haystack_session_ids=["future", "answer_gold", "old"],
                haystack_sessions=[[dict(role="user", content="future-only")],
                                   [dict(role="user", content="I moved west", has_answer=True)],
                                   [dict(role="assistant", content="general advice")]])


def test_allowlisted_projection_and_cutoff_prevent_model_facing_label_leaks():
    case = project(fixture(), "L01")
    assert set(case) == {"case", "question", "day", "turns"}
    assert "gold" not in str(case)
    assert "future-only" not in str(case)
    assert [item.session_id for item in events(case)] == [3, 2]
    assert [item.role for item in events(case)] == ["assistant", "user"]
    assert evidence_labels(fixture()) == ({"2"}, {"2/1"})
    assert recall(["2/1"], {"2"}, {"2/1"}, False) == ([1, 1], [1, 1])


def test_balanced_metadata_sample_without_answer_access():
    meta = [{"question_id": f"{kind}-{i}", "question_type": kind}
            for kind in TYPES for i in range(3)]
    meta += [{"question_id": f"other{i}_abs", "question_type": TYPES[0]} for i in range(4)]
    selected = choose(meta, 32491)
    assert selected == choose(list(reversed(meta)), 32491)
    assert len(set(selected)) == 14
    assert Counter(e["question_type"] for e in meta
                   if e["question_id"] in selected[:-2]) == dict.fromkeys(TYPES, 2)


def test_blind_bm25_prefers_literal_match_and_recalls_only_presented_sources():
    records = transcript(events(project(fixture(), "L01")))
    ranked = bm25("moved west", records)
    assert ranked[0].source.reference == "2/1"
    assert recall(["3/1"], {"2"}, {"2/1"}, False) == ([0, 1], [0, 1])
    assert recall(["2/1"], {"2"}, {"2/1"}, True) == (None, None)


def test_empty_managed_state_and_abstention_are_explicit():
    turns = events(project(fixture(), "L01"))
    assert managed_fields(TemporalMemory(), turns, turns[-1].observed_on) == ([], 0)
    assert audit_prefix([], turns)["source_restriction_signals"] == 0
    reference = fixture()
    assert judge_prediction(None, None, reference, {"status": "abstained"}) == "incorrect"
    reference["question_id"] += "_abs"
    assert judge_prediction(None, None, reference, {"status": "abstained"}) == "correct"
    assert judge_prediction(None, None, reference, {"status": "invalid"}) == "invalid-reader"
