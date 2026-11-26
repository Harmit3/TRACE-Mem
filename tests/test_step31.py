"""Step 31 regressions for frozen caps, scoring, and replay instrumentation."""

from collections import Counter
import json

from scripts.run_step30 import DESIGN, ENTITY, generate
from scripts.run_step31 import PROTOCOL, answer_score
from trace_mem.llm_tasks import LLMTasks, MockProvider
from trace_mem.memora_benchmark import run_suite


def test_all_five_planning_horizons_are_exogenous():
    design = json.loads(PROTOCOL.read_bytes())
    assert [p * 5 // 100 for p in design["horizon_percent"]] == [2, 3, 5, 7, 10]
    assert design["budgets"] == [0, 10, 25, 50, 100]


def test_reader_keeps_contradictory_answers_in_error_denominator():
    assert answer_score(None, set(), "Grove") == "abstained"
    assert answer_score("other field", set(), "Grove") == "incorrect"
    assert answer_score("Hill", {"Hill"}, "Grove") == "incorrect"
    assert answer_score("Grove and Hill", {"Grove", "Hill"}, "Grove") == "contradictory"
    assert answer_score("Grove", {"Grove"}, "Grove") == "correct"


def test_decision_hook_preserves_frozen_replay_and_reports_stale_targets():
    data = next(generate(json.loads(DESIGN.read_bytes())))
    provider = MockProvider(lambda *_: '{"verdict":"update"}')
    tasks = LLMTasks(provider)
    options = dict(entity=ENTITY, models={}, builders={}, mode="fixed", cap=5, seed=7,
                   methods=("B3",))
    plain, stats = run_suite(data["events"], data["claims"], tasks, **options)["B3"]
    observed = Counter()

    def observe(method, item, live, target, remaining, verdict, applied, failed, memory):
        if verdict is None:
            return
        assert method == "B3"
        assert not failed
        assert remaining == 5 - observed["attempts"]
        observed["attempts"] += 1
        if applied:
            assert live == target
            assert memory.trace[-1].fact_id == item.fact_id
        else:
            assert live != target
            observed["stale"] += 1

    instrumented, instrumented_stats = run_suite(
        data["events"], data["claims"], tasks, **options, decision_observer=observe)["B3"]
    assert plain.trace == instrumented.trace
    assert stats == instrumented_stats
    assert observed["attempts"] == stats["verification_attempts"] == 5
    assert observed["stale"] == stats["stale_targets"] > 0
