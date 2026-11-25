"""Freeze and run a small local v3 feasibility pilot."""

import argparse
from collections import Counter
from copy import deepcopy
from datetime import date
import itertools
import json
from pathlib import Path
from statistics import correlation, pvariance

from scripts.compare_local_verifiers import MODE, QWEN, SETTINGS, freeze
from scripts.updateset_v2_pilot import PROMPT_SCHEMA, QWEN_DIGEST, _snapshot
from trace_mem.baselines import PreparedClaim, _apply, _apply_verdict, _eligible_target
from trace_mem.controller import FEATURE_NAMES
from trace_mem.data.memora import Event
from trace_mem.data.updateset_v2 import canonical, rows_bytes, sha
from trace_mem.data.updateset_v3 import cases
from trace_mem.features_v3 import CachedMiniLM, MINILM, MINILM_REVISION, NLI, NLI_REVISION, V3Features
from trace_mem.llm_tasks import LLMTasks
from trace_mem.memory import Fact, Source, TemporalMemory
from trace_mem.providers import ChatProvider, ProviderConfig, ProviderError
from trace_mem.verification import Budget


SPLIT_CAP = 8
REQUEST_CAP = 48


def specification() -> dict:
    return {
        "dataset_sha256": sha(rows_bytes(cases())), "partitions": ["train", "calibration", "evaluation"],
        "selection": "all 24 authored cases in declared order", "split_verification_cap": SPLIT_CAP,
        "one_verification_per_case": True, "request_cap": REQUEST_CAP,
        "features": FEATURE_NAMES, "definitions": "v3-evidence-1",
        "embedding": {"model": MINILM, "revision": MINILM_REVISION, "device": "cpu",
                      "precision": "float32", "max_length": 256,
                      "torch": "2.10.0+cpu", "transformers": "5.22.2", "threads": 4},
        "nli": {"model": NLI, "revision": NLI_REVISION, "pilot_enabled": False},
        "verifier": {"model": QWEN, "digest": QWEN_DIGEST, "mode": MODE,
                     "prompt_schema_sha256": PROMPT_SCHEMA, "temperature": 0, **SETTINGS},
        "criteria": {"preserve_all_cases": True, "min_variable_available_features": 4,
                     "max_technical_failures": 2, "no_ids_or_gold_in_model_payloads": True},
    }


def generate(output: Path) -> dict:
    records = cases()
    review = [{k: v for k, v in row.items() if k != "gold"} for row in records if row["gold"] is None]
    paths = {"cases.jsonl": rows_bytes(records), "pending-review.jsonl": rows_bytes(review)}
    spec = specification() | {"files": {name: sha(data) for name, data in paths.items()}}
    output.mkdir(parents=True, exist_ok=False)
    for name, data in paths.items():
        (output / name).write_bytes(data)
    (output / "manifest.json").write_bytes(canonical(spec) + b"\n")
    return spec


def _b2(memory, entity, item):
    _apply(memory, entity, item.claim, item.source, item.fact_id, "B2", None, None, None)


def collect(case: dict, tasks: LLMTasks, builder: V3Features, budget: Budget) -> dict:
    observed = date.fromisoformat(case["observed_on"])
    original = case["old"]
    old_day = date.fromisoformat(original["observed_on"])
    entity = case["id"] + "/person"
    old = Fact(case["id"] + "/prior", entity, original["predicate"], original["value"],
               Source(old_day, "prior", original["kind"]), old_day)
    transcript = case["transcript"]
    focal = Event(observed, 2, len(transcript), "user", transcript[-1]["text"], case["kind"])
    row = {key: case[key] for key in ("id", "split", "family")}
    row.update(status="ineligible", helpful=None)
    try:
        claims = tasks.extract(focal)
    except ProviderError:
        return row | {"status": "extraction_failure"}
    prefix = TemporalMemory()
    prefix.accept(old)
    for index, claim in enumerate(claims):
        source = Source(observed, "focal", case["kind"])
        item = PreparedClaim(claim, source, f"candidate/{index}")
        target = _eligible_target(prefix, entity, claim)
        if target is None or target.fact_id != old.fact_id:
            _b2(prefix, entity, item)
            continue
        if budget.remaining == 0:
            return row | {"status": "budget_exhausted"}
        features = builder(claim, target, entity=entity, source=source,
                           budget_remaining_fraction=budget.remaining / budget.limit)
        verified = deepcopy(prefix)
        _b2(prefix, entity, item)
        failures = budget.failures
        verdict = budget.call(lambda c, f: tasks.verify(c, f, conversation=tuple(
            f'{turn["role"]}: {turn["text"]}' for turn in transcript)), claim, target)
        row.update(features=features, before=(_snapshot(prefix, old, observed),
                                               _snapshot(prefix, old, old_day)))
        if budget.failures > failures:
            return row | {"status": "verification_failure"}
        _apply_verdict(verified, entity, item, target, verdict)
        after = (_snapshot(verified, old, observed), _snapshot(verified, old, old_day))
        gold = case["gold"]
        expected = ((gold["current"].casefold(),), (gold["prior"].casefold(),)) if gold else None
        return row | {"status": "verified", "after": after, "verdict": verdict,
                      "helpful": row["before"] != expected and after == expected if gold else None,
                      "harmful": row["before"] == expected and after != expected if gold else None,
                      "unchanged": row["before"] == after}
    return row


def audit(rows: list[dict]) -> dict:
    observed = [row for row in rows if "features" in row]
    columns = {name: [row["features"][i] for row in observed] for i, name in enumerate(FEATURE_NAMES)}
    defined = {k: v for k, v in columns.items() if all(x is not None for x in v) and len(set(v)) > 1}
    split_results = {}
    for split in ("train", "calibration", "evaluation"):
        group = [row for row in rows if row["split"] == split]
        split_results[split] = {
            "cases": len(group), "statuses": dict(Counter(row["status"] for row in group)),
            "positive": sum(row["helpful"] is True for row in group),
            "negative": sum(row["helpful"] is False for row in group),
            "pending": sum(row["status"] == "verified" and row["helpful"] is None for row in group),
            "harmful": sum(row.get("harmful") is True for row in group),
            "positive_families": len({row["family"] for row in group if row["helpful"] is True}),
            "negative_families": len({row["family"] for row in group if row["helpful"] is False}),
            "unchanged": sum(row.get("unchanged") is True for row in group),
        }
    failures = sum(row["status"].endswith("_failure") for row in rows)
    return {
        "splits": split_results,
        "features": {key: {"unique": len(set(x for x in values if x is not None)),
                           "missing": values.count(None),
                           "variance": pvariance([x for x in values if x is not None])
                           if any(x is not None for x in values) else None}
                     for key, values in columns.items()},
        "pearson_nonconstant": {f"{a}:{b}": correlation(defined[a], defined[b])
                                for a, b in itertools.combinations(defined, 2)},
        "technical_gate": len(rows) == len(cases()) and len(defined) >= 4 and failures <= 2,
    }


def pilot(dataset: Path, output: Path) -> dict:
    import torch
    import transformers

    records = cases()
    manifest = json.loads((dataset / "manifest.json").read_bytes())
    if (manifest["dataset_sha256"] != sha(rows_bytes(records))
            or any(sha((dataset / name).read_bytes()) != checksum for name, checksum in manifest["files"].items())
            or any(manifest[key] != json.loads(canonical(value)) for key, value in specification().items())):
        raise ValueError("Frozen v3 inputs changed")
    identity = freeze(QWEN_DIGEST)
    if (identity["prompt_schema_sha256"] != PROMPT_SCHEMA
            or torch.__version__ != manifest["embedding"]["torch"]
            or transformers.__version__ != manifest["embedding"]["transformers"]):
        raise ValueError("Pinned model settings or dependencies changed")
    torch.set_num_threads(4)
    builder = V3Features(CachedMiniLM())
    output.mkdir(parents=True, exist_ok=False)
    provider = ChatProvider(ProviderConfig("ollama", QWEN, REQUEST_CAP, **SETTINGS),
                            output / "responses.sqlite")
    tasks = LLMTasks(provider, verification_mode=MODE)
    budgets = {split: Budget(SPLIT_CAP) for split in manifest["partitions"]}
    rows = [collect(case, tasks, builder, budgets[case["split"]]) for case in records]
    (output / "outcomes.jsonl").write_bytes(rows_bytes(rows))
    report = audit(rows) | {"dataset_sha256": manifest["dataset_sha256"],
                            "outcomes_sha256": sha(rows_bytes(rows)), "usage": provider.stats()}
    (output / "report.json").write_bytes(canonical(report) + b"\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "pilot"))
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if Path("data").resolve() not in args.dataset.resolve().parents:
        parser.error("Use an ignored dataset path under data/")
    if args.command == "generate":
        print(json.dumps(generate(args.dataset), sort_keys=True))
    else:
        if args.output is None or Path("results").resolve() not in args.output.resolve().parents:
            parser.error("Use an ignored directory under results/")
        print(json.dumps(pilot(args.dataset, args.output), sort_keys=True))
