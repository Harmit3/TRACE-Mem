"""Generate and run the preregistered TRACE-UpdateSet v2 local pilot."""

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path

from scripts.compare_local_verifiers import MODE, QWEN, SETTINGS, freeze
from trace_mem.baselines import run_baseline
from trace_mem.data.memora import Event
from trace_mem.data.updateset_v2 import read_release, rows_bytes, sha, write_release
from trace_mem.llm_tasks import LLMTasks
from trace_mem.memory import Fact, Source, TemporalMemory
from trace_mem.providers import ChatProvider, ProviderConfig, ProviderError
from trace_mem.verification import Budget


QWEN_DIGEST = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"
PROMPT_SCHEMA = "186d105583c4fa4ecba72b82f9179acd8c140d72dc661679911654a5de8a8eb8"


def _snapshot(memory: TemporalMemory, fact: Fact, day: date) -> tuple[str, ...]:
    return tuple(sorted(item.value.casefold() for item in memory.retrieve(
        fact.entity, fact.predicate, as_of=day,
    )))


def paired_case(case: dict, tasks: LLMTasks) -> dict:
    """Evaluate one focal turn without passing case metadata or gold to providers."""
    observed = date.fromisoformat(case["observed_on"])
    old = case["old_fact"]
    old_day = date.fromisoformat(old["observed_on"])
    fact = Fact(old["id"], case["persona"], old["predicate"], old["value"],
                Source(old_day, old["reference"]), old_day)
    conversation = case["conversation"]
    event = Event(observed, 2, len(conversation), "user", conversation[-1]["text"])
    budget = Budget(1)

    # Capture the first extraction response and reuse it in the second replay.
    # No claim is created by the dataset generator.
    response = None

    def complete(prompt, payload):
        nonlocal response
        if response is None:
            response = tasks.complete(prompt, payload)
        return response

    def verify(claim, prior):
        return tasks.verify(claim, prior, conversation=tuple(
            f'{turn["role"]}: {turn["text"]}' for turn in conversation))

    kwargs = {"entity": fact.entity, "method": "B2", "initial_facts": (fact,)}
    try:
        unverified = run_baseline((event,), complete, **kwargs)
    except ProviderError:
        return {"case_id": case["case_id"], "split": case["split"], "status": "extraction_failure"}
    verified = run_baseline(
        (event,), complete, budget=budget, should_verify=lambda claim, target, cap: target.fact_id == fact.fact_id,
        verify=verify, **kwargs,
    )
    before = (_snapshot(unverified, fact, observed), _snapshot(unverified, fact, old_day))
    after = (_snapshot(verified, fact, observed), _snapshot(verified, fact, old_day))
    gold = case["gold"]
    target = ((gold["current_value"].casefold(),), (gold["preserve_prior_value"].casefold(),)) if gold else None
    helpful = None if not budget.attempts or budget.failures or target is None else before != target and after == target
    return {
        "case_id": case["case_id"], "split": case["split"],
        "status": "verification_failure" if budget.failures else "ok",
        "eligible": bool(budget.attempts),
        "unchanged_trace": unverified.trace == verified.trace,
        "unchanged_anchor": before == after,
        "before_correct": before == target if target else None,
        "after_correct": after == target if target else None,
        "verification_helpful": helpful,
        "harmful": helpful is False and before == target and after != target,
        "unverified_operations": [step.operation for step in unverified.trace[1:]],
        "verified_operations": [step.operation for step in verified.trace[1:]],
    }


def summarize(rows: list[dict]) -> dict:
    counts = {split: Counter() for split in ("train", "validation")}
    for row in rows:
        count = counts[row["split"]]
        count["cases"] += 1
        count[row["status"]] += 1
        if row["status"] != "ok":
            continue
        count["eligible" if row["eligible"] else "no_eligible_conflict"] += 1
        count["unchanged_trace" if row["unchanged_trace"] else "changed_trace"] += 1
        count["unchanged_anchor" if row["unchanged_anchor"] else "changed_anchor"] += 1
        if row["eligible"]:
            label = row["verification_helpful"]
            count["pending_gold" if label is None else "positive" if label else "negative"] += 1
            count["harmful"] += row["harmful"]
    return {key: dict(value) for key, value in counts.items()}


def pilot(dataset: Path, output: Path) -> dict:
    cases, manifest = read_release(dataset)
    frozen = freeze(QWEN_DIGEST)
    if frozen["prompt_schema_sha256"] != PROMPT_SCHEMA or frozen["mode"] != MODE:
        raise ValueError("Validated verifier configuration changed")
    selected = set(manifest["pilot_ids"])
    output.mkdir(parents=True, exist_ok=True)
    artifact = output / "pilot.jsonl"
    if artifact.exists():
        raise FileExistsError(artifact)
    provider = ChatProvider(ProviderConfig("ollama", QWEN, 2 * len(selected), **SETTINGS),
                            output / "responses.sqlite")
    tasks = LLMTasks(provider, verification_mode=MODE)
    rows = [paired_case(case, tasks) for case in cases if case["case_id"] in selected]
    content = rows_bytes(rows)
    report = {
        "source_hashes": manifest["files"], "pilot_ids_sha256": sha(rows_bytes(manifest["pilot_ids"])),
        "pilot_outcomes_sha256": sha(content), "freeze": frozen,
        "split_counts": summarize(rows), "usage": provider.stats(),
    }
    with artifact.open("xb") as file:
        file.write(content)
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "pilot"))
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if Path("data").resolve() not in args.dataset.resolve().parents:
        parser.error("Use an ignored directory under data/")
    if args.command == "generate":
        print(json.dumps(write_release(args.dataset), sort_keys=True))
    else:
        if args.output is None or Path("results").resolve() not in args.output.resolve().parents:
            parser.error("Use an ignored directory under results/")
        print(json.dumps(pilot(args.dataset, args.output), sort_keys=True))
