"""Contract checks for the frozen controller reevaluation."""

from dataclasses import replace
import json

from scripts.run_memora import ARTIFACTS
from scripts.replay_memora_full import make_adaptive
from scripts.run_step30 import (DESIGN, ENTITY, apply, cap_for, dataset_hash,
                                evaluate_history, generate, memory_metrics, oracle, project,
                                validate_reference)
from scripts.summarize_step30 import paired_interval, summarize
from trace_mem.evidence_index_v2 import EvidenceIndexV2
from trace_mem.features_v3 import V3Features
from trace_mem.llm_tasks import LLMTasks, MockProvider
from trace_mem.memory import TemporalMemory
from trace_mem.providers import ProviderError
from trace_mem.semantic import NLIScores
from trace_mem.training import load_model


def histories():
    return list(generate(json.loads(DESIGN.read_bytes())))


def test_design_hash_reference_count_and_oracle():
    data = histories()
    assert dataset_hash(data) == json.loads(DESIGN.read_bytes())["dataset_sha256"]
    assert len(data) == 100
    assert len({h["family"] for h in data}) == 10
    assert sum(map(validate_reference, data)) == 500
    for h in data:
        metrics = memory_metrics(oracle(h), h)
        assert metrics["current"] == 6
        assert metrics["historical"] == 5
        assert metrics["authorized_deletion"] == metrics["deletion"] == 2
    for percentage, requests in {0: 0, 10: 50, 25: 125, 50: 250, 100: 500}.items():
        assert sum(cap_for(percentage, i) for i in range(len(data))) == requests


def test_projection_denies_deferred_values_and_private_fields():
    h = histories()[0]
    memory = TemporalMemory()
    for item in h["claims"]:
        if item.claim.intent == "delete":
            continue
        if item.fact_id in h["decisions"]:
            item = replace(item, claim=replace(item.claim, intent="uncertain"))
        apply(memory, item)
    proposals = {d["proposal"] for d in h["decisions"].values()}
    assert memory.retrieve(ENTITY, "private note", as_of=h["start"])
    for cutoff in (h["start"], h["final"]):
        index = EvidenceIndexV2(project(memory, h, cutoff), "test")
        embedded = []

        def embed(texts):
            embedded.extend(texts[1:])
            return [[1, 0] for _ in texts]

        handle = index.retrieve("previous routing information", cutoff, embed, k=20)
        values = {fact.value for fact in index.materialize(handle, ENTITY)}
        assert h["initial"] in values
        assert proposals.isdisjoint(embedded)
        assert all(h["private"] not in text for text in embedded)
        index.rebuild((), "revoked")
        assert index.materialize(handle, ENTITY) == ()


def test_paired_family_bootstrap_is_seeded_and_resamples_families():
    groups = {"a": [0.0, 0.5], "b": [-0.25], "c": [0.75]}
    out = paired_interval(groups, 2000, 9001)
    assert out == paired_interval(groups, 2000, 9001)
    assert out["difference"] == 0.25
    assert out["families"] == 3
    assert out["lower"] <= 0 <= out["upper"]


def test_complete_mocked_history_preserves_caps_and_failed_readings():
    h = histories()[0]
    config = json.loads(DESIGN.read_bytes())
    models = {"T1": load_model(ARTIFACTS / "full.json"),
              "T1-no-NLI": load_model(ARTIFACTS / "no_nli.json")}

    def embed(values):
        return [[1, 0] for _ in values]

    def respond(task, payload):
        assert h["private"] not in payload
        if task.startswith("verify"):
            assert "expected" not in json.loads(payload)
            return '{"verdict":"update"}'
        raise ProviderError("mock rejected unsupported reader output")

    full = V3Features(embed, lambda *_: NLIScores(0.2, 0.4, 0.4))
    reduced = V3Features(embed)
    builders = {"T1": full, "T1-no-NLI": reduced, "T2": full, "H-paced": reduced}
    adaptive = make_adaptive(5, [(1, 0.2, 0, 0, 0, 0, 0, 1)], models["T1"])
    provider = MockProvider(respond)
    tasks = LLMTasks(provider, verification_mode="direct-v2")
    result = evaluate_history(h, 0, config, tasks, models, builders, adaptive, embed,
                              {"short": provider, "reasoning": provider})
    assert len(result["rows"]) == 140
    assert all(row["authorized_deletion"] == 2 for row in result["rows"])
    assert all(row["verification_attempts"] <= row["budget_cap"] for row in result["rows"])
    assert all(row["verification_attempts"] == row["budget_cap"]
               for row in result["rows"] if row["mode"] == "fixed")
    aggregate = summarize({"histories": [result], "families": 1}, config)
    assert len(aggregate["random_seeds"]) == 50
    assert aggregate["oracle"]["qa"]["short"] == dict(correct=0, abstained=0, error=1, total=1)
