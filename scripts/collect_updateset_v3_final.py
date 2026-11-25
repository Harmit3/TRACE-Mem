"""Frozen longitudinal collection and audit for TRACE-UpdateSet v3."""

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from datetime import date
import itertools
import json
import math
from pathlib import Path
from statistics import correlation, pvariance

from scripts.compare_local_verifiers import MODE, QWEN, SETTINGS, freeze
from scripts.updateset_v2_pilot import PROMPT_SCHEMA, QWEN_DIGEST, _snapshot
from trace_mem.baselines import PreparedClaim, _apply, _apply_verdict, _eligible_target
from trace_mem.controller import FEATURE_NAMES
from trace_mem.data.memora import Event
from trace_mem.data.updateset_v2 import canonical, sha
from trace_mem.data.updateset_v3_final import SEED, SIZES, generate
from trace_mem.features_v3 import CachedMiniLM, MINILM_REVISION, NLI_REVISION, V3Features, pinned_nli
from trace_mem.llm_tasks import LLMTasks
from trace_mem.memory import Fact, Source, TemporalMemory
from trace_mem.providers import ChatProvider, LimitExceeded, ProviderError, ProviderConfig
from trace_mem.verification import Budget


CAP = 1200


def encode(row) -> bytes:
    return json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      default=lambda item: item.isoformat()).encode() + b"\n"


def save(path: Path, content: bytes) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def dataset_files() -> dict[str, bytes]:
    histories = generate()
    review = []
    for history in histories:
        for index, turn in enumerate(history["turns"], 1):
            if turn["gold"] is None:
                review.append({"id": history["id"], "turn": index, "prior": history["prior"],
                               "timeline": [{k: v for k, v in item.items() if k != "gold"}
                                            for item in history["turns"][:index]]})
    return {
        "histories.jsonl": b"".join(map(encode, histories)),
        "pending-review.jsonl": b"".join(map(encode, review)),
    }


def prepare(path: Path) -> dict:
    files = dataset_files()
    histories = generate()
    manifest = {
        "version": "v3-longitudinal-1", "seed": SEED, "histories": SIZES,
        "decision_points": sum(len(row["turns"]) for row in histories),
        "families": {split: len({row["family"] for row in histories if row["split"] == split})
                     for split in SIZES},
        "pending_gold": dict(Counter(row["split"] for row in histories for turn in row["turns"]
                                     if turn["gold"] is None)),
        "files": {name: sha(content) for name, content in files.items()},
    }
    path.mkdir(parents=True, exist_ok=False)
    for name, content in files.items():
        save(path / name, content)
    save(path / "manifest.json", encode(manifest))
    return manifest


def _b2(memory, entity, item):
    _apply(memory, entity, item.claim, item.source, item.fact_id, "B2", None, None, None)


def collect(history: dict, tasks: LLMTasks, builder: V3Features) -> dict:
    initial = history["prior"]
    prior_day = date.fromisoformat(initial["observed_on"])
    entity = history["id"] + "/person"
    old = Fact("prior", entity, initial["predicate"], initial["value"],
               Source(prior_day, "prior", initial["kind"]), prior_day)
    memory = TemporalMemory()
    memory.accept(old)
    budget = Budget(history["cap"])
    predicate = "employer" if old.predicate == "job" else "home"
    conversation = [f"user: My {predicate} is {old.value}."]
    steps = []
    for turn, record in enumerate(history["turns"], 1):
        day = date.fromisoformat(record["date"])
        message = record["message"]
        conversation.extend((f"assistant: Is there anything new about your {predicate}?",
                             f"user: {message}"))
        source = Source(day, f"turn/{turn}", record["source_kind"])
        step = {"turn": turn, "status": "ok", "candidates": []}
        steps.append(step)
        try:
            claims = tasks.extract(Event(day, turn, 1, "user", message, source.kind))
        except LimitExceeded:
            raise
        except ProviderError:
            step["status"] = "extraction_failure"
            continue
        for index, claim in enumerate(claims):
            item = PreparedClaim(claim, source, f"turn/{turn}/{index}")
            target = _eligible_target(memory, entity, claim)
            candidate = {"id": item.fact_id, "claim": asdict(claim), "source": asdict(source),
                         "status": "ineligible", "helpful": None}
            step["candidates"].append(candidate)
            if target is None or target.predicate != old.predicate:
                _b2(memory, entity, item)
                continue
            if not budget.remaining:
                candidate["status"] = "budget_exhausted"
                _b2(memory, entity, item)
                continue
            vector = builder(claim, target, entity=entity, source=source,
                             budget_remaining_fraction=budget.remaining / budget.limit)
            if len(vector) != len(FEATURE_NAMES) or any(x is None or not math.isfinite(x) for x in vector):
                raise ValueError("V3 collection requires all eight finite features")
            alternate = deepcopy(memory)
            candidate.update(features=vector, target=asdict(target), prior_calls=budget.attempts)
            _b2(memory, entity, item)
            before = (_snapshot(memory, old, day), _snapshot(memory, old, prior_day))
            candidate.update(unverified=before, unverified_transition=asdict(memory.trace[-1]))
            budget.attempts += 1
            try:
                verdict = tasks.verify(claim, target, conversation=tuple(conversation))
            except LimitExceeded:
                raise
            except ProviderError:
                budget.failures += 1
                candidate["status"] = "verification_failure"
                continue
            _apply_verdict(alternate, entity, item, target, verdict)
            after = (_snapshot(alternate, old, day), _snapshot(alternate, old, prior_day))
            gold = record["gold"]
            expected = ((gold["current"].casefold(),), (gold["prior"].casefold(),)) if gold else None
            candidate.update(status="verified", verified=after, verdict=verdict, gold=gold,
                             verified_transition=asdict(alternate.trace[-1]),
                             helpful=before != expected and after == expected if gold else None,
                             harmful=before == expected and after != expected if gold else None,
                             unchanged=before == after)
    return {k: history[k] for k in ("id", "split", "family", "cap")} | {
        "attempts": budget.attempts, "failures": budget.failures, "steps": steps,
    }


def audit(histories: list[dict]) -> dict:
    groups = {}
    for split in SIZES:
        part = [row for row in histories if row["split"] == split]
        steps = [step for row in part for step in row["steps"]]
        candidates = [(row, c) for row in part for step in row["steps"] for c in step["candidates"]]
        vectors = [c["features"] for _, c in candidates if "features" in c]
        columns = dict(zip(FEATURE_NAMES, zip(*vectors)))
        varying = {name: values for name, values in columns.items() if len(set(values)) > 1}
        known = [c for _, c in candidates if c["status"] == "verified"]
        groups[split] = {
            "histories": len(part), "decision_points": len(steps),
            "families": len({row["family"] for row in part}),
            "extraction_failures": sum(step["status"] == "extraction_failure" for step in steps),
            "candidate_status": dict(Counter(c["status"] for _, c in candidates)),
            "positive": sum(c["helpful"] is True for c in known),
            "negative": sum(c["helpful"] is False for c in known),
            "pending_gold": sum(c["helpful"] is None for c in known),
            "harmful": sum(c["harmful"] is True for c in known),
            "unchanged": sum(c["unchanged"] for c in known),
            "changed_still_incorrect": sum(c["helpful"] is False and not c["harmful"]
                                           and not c["unchanged"] for c in known),
            "positive_histories": len({row["id"] for row, c in candidates if c["helpful"] is True}),
            "negative_histories": len({row["id"] for row, c in candidates if c["helpful"] is False}),
            "positive_families": len({row["family"] for row, c in candidates if c["helpful"] is True}),
            "negative_families": len({row["family"] for row, c in candidates if c["helpful"] is False}),
            "features": {name: {"distinct": len(set(values)), "min": min(values), "max": max(values),
                                "variance": pvariance(values)} for name, values in columns.items()},
            "missing_eligible_vectors": sum(c["status"] in ("verified", "verification_failure")
                                            and "features" not in c for _, c in candidates),
            "unique_vectors": len({tuple(vector) for vector in vectors}),
            "unique_without_nli": len({tuple(vector[:1] + vector[2:]) for vector in vectors}),
            "pearson_nonconstant": {f"{a}:{b}": correlation(varying[a], varying[b])
                                    for a, b in itertools.combinations(varying, 2)},
        }
    return groups


def run(dataset: Path, model: Path, output: Path) -> dict:
    import torch
    import transformers

    manifest = json.loads((dataset / "manifest.json").read_bytes())
    expected = dataset_files()
    if (manifest["files"] != {k: sha(v) for k, v in expected.items()}
            or any((dataset / k).read_bytes() != v for k, v in expected.items())):
        raise ValueError("Frozen dataset files changed")
    settings = freeze(QWEN_DIGEST)
    if settings["prompt_schema_sha256"] != PROMPT_SCHEMA:
        raise ValueError("Pinned verifier prompt changed")
    files = ("scripts/collect_updateset_v3_final.py", "trace_mem/data/updateset_v3_final.py",
             "trace_mem/features_v3.py", "trace_mem/baselines.py", "trace_mem/claims.py",
             "trace_mem/providers.py", "trace_mem/llm_tasks.py")
    spec = {"dataset": manifest, "verifier": settings, "features": FEATURE_NAMES,
            "minilm": MINILM_REVISION, "nli": NLI_REVISION, "threads": 4, "cap": CAP,
            "torch": torch.__version__, "transformers": transformers.__version__,
            "code": {path: sha(Path(path).read_text(encoding="utf-8").encode()) for path in files}}
    output.mkdir(parents=True, exist_ok=True)
    freeze_file = output / "freeze.json"
    if freeze_file.exists() and freeze_file.read_bytes() != canonical(spec):
        raise ValueError("Cannot resume with different settings or sources")
    save(freeze_file, canonical(spec))
    torch.set_num_threads(4)
    builder = V3Features(CachedMiniLM(), pinned_nli(model))
    provider = ChatProvider(ProviderConfig("ollama", QWEN, CAP, **SETTINGS), output / "responses.sqlite")
    tasks = LLMTasks(provider, verification_mode=MODE)
    checkpoints = output / "histories"
    checkpoints.mkdir(exist_ok=True)
    histories = []
    for index, history in enumerate(generate(), 1):
        path = checkpoints / f"{index:04}.json"
        if path.exists():
            result = json.loads(path.read_bytes())
            if result["id"] != history["id"]:
                raise ValueError("Checkpoint does not match frozen ordering")
        else:
            result = collect(history, tasks, builder)
            save(path, encode(result))
        histories.append(result)
        if index % 10 == 0:
            print(json.dumps({"histories": index, "decision_points": index * 3,
                              "usage": provider.stats()}), flush=True)
    data = b"".join(map(encode, histories))
    report = {"outcomes_sha256": sha(data), "groups": audit(histories), "usage": provider.stats()}
    save(output / "outcomes.jsonl", data)
    save(output / "report.json", encode(report))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if Path("data").resolve() not in args.dataset.resolve().parents:
        parser.error("Use an ignored directory under data/")
    if args.command == "prepare":
        print(json.dumps(prepare(args.dataset), sort_keys=True))
    else:
        if (args.model is None or args.output is None
                or Path("results").resolve() not in args.output.resolve().parents):
            parser.error("Provide a local model directory and ignored results directory")
        print(json.dumps(run(args.dataset, args.model, args.output), sort_keys=True))
