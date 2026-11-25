"""Collect candidate-level TRACE-UpdateSet v2 outcomes from frozen B2 prefixes."""

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from datetime import date
import json
from pathlib import Path
import statistics

from scripts.compare_local_verifiers import MODE, QWEN, SETTINGS, freeze
from scripts.updateset_v2_pilot import PROMPT_SCHEMA, QWEN_DIGEST, _snapshot
from trace_mem.baselines import PreparedClaim, _apply, _apply_verdict, _eligible_target
from trace_mem.controller import FEATURE_NAMES, features_for
from trace_mem.data.memora import Event
from trace_mem.data.updateset_v2 import canonical, read_release, sha
from trace_mem.llm_tasks import LLMTasks
from trace_mem.memory import Fact, Source, TemporalMemory
from trace_mem.providers import ChatProvider, ProviderConfig, ProviderError, LimitExceeded


CAP = 5000
PROTOCOL = "v2-candidate-prefix-1"


def _b2(memory, entity, item):
    _apply(memory, entity, item.claim, item.source, item.fact_id, "B2", None, None, None)


def collect_case(case: dict, tasks: LLMTasks, *, pilot: bool) -> dict:
    observed = date.fromisoformat(case["observed_on"])
    old = case["old_fact"]
    prior_day = date.fromisoformat(old["observed_on"])
    fact = Fact(old["id"], case["persona"], old["predicate"], old["value"],
                Source(prior_day, old["reference"]), prior_day)
    conversation = case["conversation"]
    focal = Event(observed, 2, len(conversation), "user", conversation[-1]["text"])
    source = Source(observed, f'{case["case_id"]}/source/{focal.turn}')
    row = {key: case[key] for key in ("case_id", "split", "family", "persona", "history")}
    row.update(pilot=pilot, status="ok", candidates=[])
    try:
        claims = tasks.extract(focal)
    except LimitExceeded:
        raise
    except ProviderError as error:
        row.update(status="extraction_failure", failure=str(error))
        return row
    prefix = TemporalMemory()
    prefix.accept(fact)
    transcript = tuple(f'{turn["role"]}: {turn["text"]}' for turn in conversation)
    for index, claim in enumerate(claims):
        item = PreparedClaim(claim, source, f'{case["case_id"]}/candidate/{index}')
        candidate = {"id": item.fact_id, "claim": asdict(claim), "source": asdict(source),
                     "status": "ineligible", "helpful": None}
        row["candidates"].append(candidate)
        target = _eligible_target(prefix, fact.entity, claim)
        if target is None or target.fact_id != fact.fact_id:
            _b2(prefix, fact.entity, item)
            continue
        # Freeze the inputs and features before both the verifier and any gold access.
        candidate.update(
            target=asdict(target), prefix_trace=[asdict(step) for step in prefix.trace],
            features=features_for(claim, target, entity=fact.entity, source=source,
                                  budget_remaining_fraction=1.0),
        )
        verified = deepcopy(prefix)
        _b2(prefix, fact.entity, item)
        before = (_snapshot(prefix, fact, observed), _snapshot(prefix, fact, prior_day))
        candidate.update(unverified=before, unverified_transition=asdict(prefix.trace[-1]))
        try:
            verdict = tasks.verify(claim, target, conversation=transcript)
        except LimitExceeded:
            raise
        except ProviderError as error:
            candidate.update(status="verification_failure", failure=str(error))
            continue
        _apply_verdict(verified, fact.entity, item, target, verdict)
        after = (_snapshot(verified, fact, observed), _snapshot(verified, fact, prior_day))
        gold = case["gold"]
        expected = ((gold["current_value"].casefold(),),
                    (gold["preserve_prior_value"].casefold(),)) if gold else None
        candidate.update(
            status="verified", verdict=verdict, verified=after, gold=gold,
            verified_transition=asdict(verified.trace[-1]),
            unchanged=before == after,
            helpful=(before != expected and after == expected) if gold else None,
            harmful=(before == expected and after != expected) if gold else None,
        )
    return row


def _encode(row: dict) -> bytes:
    return json.dumps(row, sort_keys=True, default=lambda value: value.isoformat()).encode() + b"\n"


def _save(path: Path, data: bytes) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_bytes(data)
    temp.replace(path)


def audit(rows: list[dict]) -> dict:
    groups = {}
    for split in ("train", "validation"):
        for pilot in (False, True):
            subset = [r for r in rows if r["split"] == split and r["pilot"] is pilot]
            candidates = [c for r in subset for c in r["candidates"]]
            features = [c["features"] for c in candidates if "features" in c]
            counts = Counter(c["status"] for c in candidates)
            families = Counter()
            verified_cases = set()
            for row in subset:
                for c in row["candidates"]:
                    if c["status"] != "verified":
                        continue
                    verified_cases.add(row["case_id"])
                    if c["helpful"] is not None:
                        families[row["family"]] += 1
            groups[f'{split}/{"pilot" if pilot else "nonpilot"}'] = {
                "cases": len(subset), "families_sampled": len({r["family"] for r in subset}),
                "extraction_failures": sum(r["status"] == "extraction_failure" for r in subset),
                "cases_no_eligible": sum(r["status"] == "ok" and not any(
                    "features" in c for c in r["candidates"]) for r in subset),
                "candidate_status": dict(counts), "verified_cases": len(verified_cases),
                "positive": sum(c["helpful"] is True for c in candidates),
                "negative": sum(c["helpful"] is False for c in candidates),
                "pending_gold": sum(c["status"] == "verified" and c["helpful"] is None
                                    for c in candidates),
                "harmful": sum(c.get("harmful") is True for c in candidates),
                "unchanged": sum(c.get("unchanged") is True for c in candidates),
                "labeled_by_family": dict(families),
                "positive_by_family": dict(Counter(r["family"] for r in subset
                                                    for c in r["candidates"] if c["helpful"] is True)),
                "features": {name: {"distinct": len(set(column)),
                                    "min": min(column), "max": max(column),
                                    "mean": statistics.fmean(column)}
                             for name, column in zip(FEATURE_NAMES, zip(*features))},
                "missing_feature_rows": sum(c["status"] != "ineligible"
                                             and "features" not in c for c in candidates),
            }
    return groups


def run(dataset: Path, output: Path) -> dict:
    cases, manifest = read_release(dataset)
    settings = freeze(QWEN_DIGEST)
    if settings["prompt_schema_sha256"] != PROMPT_SCHEMA or settings["mode"] != MODE:
        raise ValueError("Validated verifier configuration changed")
    paths = ("scripts/collect_updateset_v2.py", "trace_mem/baselines.py", "trace_mem/controller.py",
             "trace_mem/claims.py", "trace_mem/llm_tasks.py", "trace_mem/providers.py")
    run_spec = {
        "protocol": PROTOCOL, "source": manifest["files"], "pilot_ids": sorted(manifest["pilot_ids"]),
        "runtime": settings, "feature_names": FEATURE_NAMES,
        "code_sha256": {path: sha(Path(path).read_text(encoding="utf-8").encode()) for path in paths},
        "request_cap": CAP,
    }
    output.mkdir(parents=True, exist_ok=True)
    spec_file = output / "freeze.json"
    if spec_file.exists():
        if spec_file.read_bytes() != canonical(run_spec):
            raise ValueError("Cannot resume with changed inputs or configuration")
    else:
        _save(spec_file, canonical(run_spec))
    provider = ChatProvider(ProviderConfig("ollama", QWEN, CAP, **SETTINGS), output / "responses.sqlite")
    tasks = LLMTasks(provider, verification_mode=MODE)
    checkpoints = output / "cases"
    checkpoints.mkdir(exist_ok=True)
    pilot_ids = set(run_spec["pilot_ids"])
    rows = []
    for index, case in enumerate(cases):
        path = checkpoints / f"{index:04}.json"
        if path.exists():
            row = json.loads(path.read_bytes())
            if row["case_id"] != case["case_id"]:
                raise ValueError("Checkpoint case does not match frozen order")
        else:
            row = collect_case(case, tasks, pilot=case["case_id"] in pilot_ids)
            _save(path, _encode(row))
        rows.append(row)
        if len(rows) % 25 == 0:
            print(json.dumps({"completed": len(rows), "total": len(cases),
                              "usage": provider.stats()}), flush=True)
    data = b"".join(_encode(row) for row in rows)
    report = {"cases": len(rows), "outcomes_sha256": sha(data), "groups": audit(rows),
              "usage": provider.stats()}
    _save(output / "outcomes.jsonl", data)
    _save(output / "report.json", canonical(report))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if (Path("data").resolve() not in args.dataset.resolve().parents
            or Path("results").resolve() not in args.output.resolve().parents):
        parser.error("Use ignored data/ and results/ paths")
    print(json.dumps(run(args.dataset, args.output), sort_keys=True))
