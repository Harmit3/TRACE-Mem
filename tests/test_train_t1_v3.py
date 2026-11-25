"""Regression tests for the frozen-feature V3 training entry point."""

import json
from datetime import date

import pytest

from scripts import train_t1_v3 as v3
from trace_mem.baselines import run_t1
from trace_mem.data.memora import Event
from trace_mem.training import load_model



def fixture_stream(tmp_path):
    stream = tmp_path / "outcomes.jsonl"
    histories = []
    for split, count in (("train", 10), ("calibration", 3), ("evaluation", 4)):
        for family in range(count):
            candidates = [
                {"status": "verified", "features": [0.3, i, 1, 1, family, 0.5, i / 2, 1],
                 "helpful": bool(i)} for i in range(2)
            ]
            candidates.extend([
                {"status": "verified", "features": [0.3, 0, 1, 1, 999, 0.5, 0, 1], "helpful": None},
                {"status": "budget_exhausted", "helpful": None},
            ])
            histories.append({"split": split, "family": f"{split}-{family}",
                              "steps": [{"candidates": candidates}]})
    stream.write_text("\n".join(map(json.dumps, histories)), encoding="utf-8")
    return stream, histories


def test_partition_isolation_training_and_freeze(tmp_path, monkeypatch):
    stream, histories = fixture_stream(tmp_path)
    first = tmp_path / "first"
    monkeypatch.setattr(v3, "BOOTSTRAPS", 12)
    v3.fit(stream, first, {})
    full = load_model(first / "full.json")
    ablation = load_model(first / "no_nli.json")
    assert full.controller.means[4] == 4.5   # excludes pending extreme and calibration
    assert full.controller.weights[2] == 0
    assert ablation.controller.weights[1] == 0
    assert ablation.controller.score([0, 0, 1, 0, 0, 0, 0, 0]) == (
        ablation.controller.score([0, 1, 1, 0, 0, 0, 0, 0])
    )
    monkeypatch.setattr(v3, "plots", lambda *args: None)
    evaluated = tmp_path / "evaluation"
    v3.evaluate(stream, first, evaluated, {})
    result = json.loads((evaluated / "evaluation.json").read_bytes())
    matched = result["allocation"]["rank_matched"]
    assert {series["25"]["calls"] for series in matched.values()} == {3}
    assert matched["full"]["100"]["pending"] == 4
    assert matched["full"]["100"]["coverage_all_eligible"] == 0.75
    for history in histories:
        if history["split"] == "evaluation":
            history["steps"][0]["candidates"][0]["helpful"] = "inaccessible"
    stream.write_text("\n".join(map(json.dumps, histories)), encoding="utf-8")
    second = tmp_path / "second"
    v3.fit(stream, second, {})
    for file in first.iterdir():
        assert file.read_bytes() == (second / file.name).read_bytes()

    with (first / "full.json").open("ab") as file:
        file.write(b" ")
    with pytest.raises(ValueError, match="hash mismatch"):
        v3.evaluate(stream, first, tmp_path / "rejected", {})


def test_loaded_artifact_drives_causal_replay(tmp_path):
    stream, _ = fixture_stream(tmp_path)
    frozen = tmp_path / "fit"
    v3.fit(stream, frozen, {})
    artifact = load_model(frozen / "full.json")
    today = date(2025, 1, 2)
    events = [Event(today, 1, i + 1, "user", text) for i, text in enumerate(("A", "B", "C"))]
    seen = []

    def complete(_system, prompt):
        value = json.loads(prompt)["message"]
        return json.dumps([{"predicate": "job", "value": value, "intent": "correct",
                            "effective_on": f"2025-01-0{1 if value == 'A' else 2}"}])

    def features(_claim, _target, **kwargs):
        seen.append(kwargs["budget_remaining_fraction"])
        return (0.3, 1, 1, 1, 4.5, 0.5, 0.5, 1)

    result = run_t1(events, complete, entity="person", controller=artifact.controller,
                    threshold=0.0, calls=1, feature_builder=features,
                    verify=lambda *_: "insufficient_evidence")
    assert result.attempts == 1
    assert seen == [1]
