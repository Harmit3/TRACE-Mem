"""Leakage, deletion, budget-matching, and scoring regressions for Memora."""

from datetime import date
import json
from types import SimpleNamespace

import pytest

from scripts.score_memora_checks import aggregate_checks
from trace_mem.controller import LogisticController
from trace_mem.data.memora import Event, replay
from trace_mem.llm_tasks import LLMTasks, MockProvider
from trace_mem.memora_benchmark import METHODS, Question, answer_suite, prepare, questions, run_suite


def test_projection_never_exposes_rubric_or_operation(tmp_path):
    history = tmp_path / "persona"
    conversations = history / "conversations"
    conversations.mkdir(parents=True)
    sentinel = "gold-only-sensitive-marker"
    row = {"question_id": "q", "question": "Where?", "question_date": "2025-01-02",
           "evaluation": sentinel, "memory_evidence": sentinel, "forgetting_evidence": sentinel}
    rubric = history / "evaluation_questions_persona.json"
    rubric.write_text(json.dumps({"questions": {"remembering": [row]}}))
    session = {"date": "2025-01-01", "persona": "persona", "session_id": 1,
               "operation_details": sentinel, "operation": sentinel,
               "conversation": [{"turn": 1, "speaker": "user_agent", "message": "I live in Cedar",
                                 "share_memory": sentinel}]}
    (conversations / "session_1.json").write_text(json.dumps(session))
    query, = questions(rubric, {"remembering": [0]})
    assert query == Question("q", "remembering", "Where?", date(2025, 1, 2))
    events = tuple(replay(history))
    calls = []

    def respond(task, payload):
        assert sentinel not in payload
        calls.append(task)
        if task == "extract-v1":
            assert set(json.loads(payload)) == {"observed_on", "message"}
            return '[{"predicate":"residence","value":"Cedar","intent":"assert"}]'
        assert set(json.loads(payload)) == {"question", "facts", "as_of"}
        return '{"answer":"Cedar","citations":["1/1/0"]}'

    tasks = LLMTasks(MockProvider(respond))
    claims, failures = prepare(events, tasks)
    assert not failures and len(claims) == 1
    states = run_suite(events, claims, tasks, entity="persona", models={}, builders={},
                       mode="closed-loop", cap=0, seed=23)
    answers = answer_suite(query, states, tasks, entity="persona", k=2,
                           embed=lambda texts: [[1, 0] for _ in texts])
    assert answers["B0"]["answer"] is None
    assert all(answers[m]["answer"] == "Cedar" for m in METHODS[1:])
    assert calls == ["extract-v1"] + ["answer-v1"] * 7


def test_fixed_match_and_closed_loop_cap_with_deletion_and_failed_call():
    events = tuple(Event(date(2025, 1, i), i, 1, "user", text) for i, text in enumerate(
        ("Cedar:assert", "Fern:correct", "Birch:correct", "Cedar:delete"), 1))
    verify_payloads = []

    def respond(task, payload):
        data = json.loads(payload)
        if task == "extract-v1":
            value, intent = data["message"].split(":")
            return json.dumps([{"predicate": "residence", "value": value, "intent": intent}])
        verify_payloads.append(data)
        if data["proposed"]["value"] == "Birch":
            raise ValueError("invalid fixture response")
        return '{"verdict":"update"}'

    tasks = LLMTasks(MockProvider(respond), verification_mode="direct-v2")
    claims, _ = prepare(events, tasks)
    score = LogisticController((0,) * 8, (1,) * 8, (0,) * 8, 0)
    models = {method: SimpleNamespace(controller=score, threshold=0.5)
              for method in ("T1", "T1-no-NLI")}
    budgets = []

    def build(*args, **kwargs):
        budgets.append(kwargs["budget_remaining_fraction"])
        return (0.5, None, 1, 0, 1, 0, 0, 1)

    builders = dict.fromkeys(models, build)
    args = dict(entity="person", models=models, builders=builders, cap=2, seed=23,
                random_probability=1)
    fixed = run_suite(events, claims, tasks, mode="fixed", **args)
    live = run_suite(events, claims, tasks, mode="closed-loop", **args)
    for m in ("B3", "B4", "B5", "T1", "T1-no-NLI"):
        assert fixed[m][1]["verification_attempts"] == 2
        assert fixed[m][1]["verification_failures"] == 1
        assert live[m][1]["verification_attempts"] <= 2
    assert live["T1"][1]["verification_attempts"] == 2
    assert live["B5"][1]["verification_attempts"] == 0
    assert 0.5 in budgets
    assert all(len(row["conversation"]) == 1 for row in verify_payloads)
    for states in (fixed, live):
        memory = states["T1"][0]
        assert not memory.retrieve("person", None, as_of=date(2025, 1, 1))
        assert {f.value for f in memory.retrieve("person", None, as_of=date(2025, 1, 2))} == {"Fern"}
    assert Question("q", "remembering", "On 2025-01-02?", date(2025, 1, 4)).as_of == date(2025, 1, 2)


def test_scorer_requires_complete_external_yes_no_judgments():
    checks = [{"evaluation_question_id": "remember", "expected_answer": "yes",
               "evaluation_type": "memory_presence"},
              {"evaluation_question_id": "omit", "expected_answer": "no",
               "evaluation_type": "forgetting_absence"}]
    rubric = {"evaluation": {"evaluation_questions": checks}}
    counts = []

    def formula(*args):
        counts.append(args)
        return 0.5

    result = aggregate_checks(rubric, {"remember": "yes", "omit": "yes"}, formula)
    assert counts == [(1, 1, 0, 1)]
    assert result["fama_arithmetic"] == 0.5
    assert result["forgetting_absence_accuracy"] == 0
    with pytest.raises(ValueError, match="exactly one"):
        aggregate_checks(rubric, {"remember": "yes"}, formula)
