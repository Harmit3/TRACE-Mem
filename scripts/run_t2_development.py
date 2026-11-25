"""Frozen development-only audit and causal allocation comparison for T2."""

from argparse import ArgumentParser
from collections import defaultdict
from dataclasses import replace
from datetime import date, timedelta
import itertools
import json
from pathlib import Path
import statistics
import time

from scripts.compare_local_verifiers import MODE, QWEN, SETTINGS, checksum, local_json
from scripts.run_memora import ARTIFACTS, ROOT, sha, write
from scripts.run_memora_controlled import assess, synthetic_input
from scripts.train_t1_v3 import PINNED
from scripts.updateset_v2_pilot import PROMPT_SCHEMA, QWEN_DIGEST
from trace_mem.adaptive_verification import AdaptiveAllocation, heuristic_score, neutralized_score
from trace_mem.baselines import _eligible_target, _apply
from trace_mem.features_v3 import CachedMiniLM, V3Features, pinned_nli
from trace_mem.llm_tasks import DIRECT_V2_PROMPT, LLMTasks, RESPONSE_SCHEMAS
from trace_mem.memora_benchmark import run_suite
from trace_mem.memory import TemporalMemory
from trace_mem.providers import ChatProvider, ProviderConfig
from trace_mem.training import load_model


DESIGN = ROOT / "docs/t2_step23_freeze.json"
METHODS = ("B2", "B3", "B4", "B5", "T1", "T1-no-NLI", "T2", "H-paced")


def frozen_rows(path):
    if sha(path) != PINNED["outcomes.jsonl"]:
        raise ValueError("Unexpected V3 outcome release")
    groups = defaultdict(list)
    for line in path.read_bytes().splitlines():
        history = json.loads(line)
        groups[history["split"]].extend(c["features"] for step in history["steps"]
                                       for c in step["candidates"] if "features" in c)
    return groups


def summarize(rows, artifact):
    if not rows:
        return {"eligible": 0}
    controller = artifact.controller
    scores = [controller.score(row) for row in rows]
    transformed = [controller.score((*row[:-1], 0.5)) for row in rows]
    gains = ({"temporal": {3: 1}, "provenance": {5: 1}, "full_budget": {7: 1}})
    return {
        "eligible": len(rows), "feature_means": list(map(statistics.fmean, zip(*rows))),
        "feature_ranges": [[min(v), max(v)] for v in zip(*rows)],
        "score_min_median_max": [min(scores), statistics.median(scores), max(scores)],
        "threshold": artifact.threshold, "above_threshold": sum(v >= artifact.threshold for v in scores),
        "above_threshold_at_half_budget": sum(v >= artifact.threshold for v in transformed),
        "mean_score_if_changed": {key: statistics.fmean(controller.score(tuple(
            values.get(i, value) for i, value in enumerate(row))) for row in rows)
            for key, values in gains.items()},
    }


def ref_vectors(prepared, builder):
    memory = TemporalMemory()
    rows = []
    for item in prepared:
        target = _eligible_target(memory, "probe", item.claim)
        if target is not None:
            rows.append(builder(item.claim, target, entity="probe", source=item.source,
                                budget_remaining_fraction=1.0))
        _apply(memory, "probe", item.claim, item.source, item.fact_id, "B2", None, None, None)
    return rows


def new_fixture(history, ordinal):
    """Build fixed evidence/date metadata and gold state independently of inference."""
    from scripts.run_memora_controlled import source_claim
    from trace_mem.data.memora import Event

    anchor = date(2025, 3, 15)
    records, expected, negatives = [], [], []
    for i, (predicate, old, new, intent, text, correct) in enumerate(history["pairs"]):
        before = anchor - timedelta(days=(1, 8, 45, 100, 220)[i % 5])
        after = anchor + timedelta(days=i // 4)
        explicit = "{date}" in text
        records.append((before, predicate, old, "assert", f"Remember my {predicate} is {old}.", False))
        records.append((after, predicate, new, intent, text.format(date=after.isoformat()), explicit))
        current = anchor + timedelta(days=5)
        expected.extend(((predicate, old, before, True, "historical"),
                         (predicate, new if correct else old, current, True, "current"),
                         (predicate, old if correct else new, current, False, "current")))
        if not correct:
            negatives.append((predicate, new))
    p, v = history["deleted"]
    records.extend(((anchor, p, v, "assert", f"Remember my {p} is {v}.", False),
                    (current, p, v, "delete", f"Please delete my {p}: {v}.", False)))
    expected.extend(((p, v, anchor, False, "deletion"), (p, v, current, False, "deletion")))
    events, prepared = [], []
    for number, (day, pred, value, intent, text, explicit) in enumerate(
            sorted(records, key=lambda record: record[0]), 1):
        kind = "direct" if (number + ordinal) % 3 == 0 else "unknown"
        event = Event(day, number, 1, "user", text, kind)
        item = source_claim(event, pred, value, intent)
        events.append(event)
        prepared.append(replace(item, claim=replace(item.claim, explicit_effective_date=explicit)))
    return tuple(events), tuple(prepared), tuple(expected), tuple(negatives), current


def run(outcomes, nli, output):
    import torch

    if (ROOT / "results").resolve() not in output.resolve().parents:
        raise ValueError("Keep experiment caches under ignored results/")
    design = json.loads(DESIGN.read_bytes())
    config = design["planned_opportunities_per_history"]
    if {m["name"]: m["digest"] for m in local_json("/api/tags")["models"]}.get(QWEN) != QWEN_DIGEST:
        raise ValueError("Local Qwen digest changed")
    if checksum([DIRECT_V2_PROMPT, RESPONSE_SCHEMAS["verify-direct-v2"]]) != PROMPT_SCHEMA:
        raise ValueError("Pinned verifier prompt/schema changed")
    manifest = json.loads((ARTIFACTS / "fit-freeze.json").read_bytes())
    if any(sha(ARTIFACTS / f) != digest for f, digest in manifest["artifacts_sha256"].items()):
        raise ValueError("Frozen T1 artifact mismatch")
    groups = frozen_rows(outcomes)
    models = {key: load_model(ARTIFACTS / name) for key, name in (
        ("T1", "full.json"), ("T1-no-NLI", "no_nli.json"))}
    full = models["T1"]
    # Policy references use only training vectors and ignore helpfulness labels.
    score = lambda vector: neutralized_score(full, vector)
    adaptive = {name: AdaptiveAllocation(fn, tuple(sorted(map(fn, groups["train"]))), config)
                for name, fn in (("T2", score), ("H-paced", heuristic_score))}
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    torch.set_num_threads(4)
    embed = CachedMiniLM()
    nli_model = pinned_nli(nli)
    # Reuse deterministic semantic features for repeated policy calls on the same evidence.
    from functools import lru_cache
    raw = V3Features(embed, nli_model)

    @lru_cache(maxsize=1024)
    def neutral_features(claim, target, entity, source):
        return raw(claim, target, entity=entity, source=source, budget_remaining_fraction=1.0)

    def build(claim, target, *, entity, source, budget_remaining_fraction):
        return (*neutral_features(claim, target, entity, source)[:-1], budget_remaining_fraction)

    no_nli = V3Features(embed)

    @lru_cache(maxsize=1024)
    def no_nli_features(claim, target, *, entity, source, budget_remaining_fraction):
        return no_nli(claim, target, entity=entity, source=source,
                      budget_remaining_fraction=budget_remaining_fraction)

    builders = {"T1": build, "T1-no-NLI": no_nli_features, "T2": build, "H-paced": no_nli_features}
    past = json.loads((ROOT / "docs/memora_step22_freeze.json").read_bytes())
    downstream = [v for fixture in past["synthetic"]
                  for v in ref_vectors(synthetic_input(fixture)[1], build)]
    distribution = {split: summarize(values, full) for split, values in groups.items()}
    distribution["step22_oracle_diagnostic"] = summarize(downstream, full)
    distribution["t1_budget_logit_delta_full_vs_empty"] = full.controller.weights[-1] / full.controller.scales[-1]
    provider = ChatProvider(ProviderConfig("ollama", QWEN, 400, **SETTINGS), output / "responses.sqlite")
    tasks = LLMTasks(provider, verification_mode=MODE)
    report = []
    new_vectors = []
    for ordinal, history in enumerate(design["histories"]):
        events, prepared, expected, forbidden, current = new_fixture(history, ordinal)
        vectors = ref_vectors(prepared, build)
        new_vectors.extend(vectors)
        for mode, percent in itertools.product(("fixed", "closed-loop"), design["budgets"]):
            # The closed-loop cap uses a published nominal horizon, not a realized stream count.
            cap = (len(vectors) if mode == "fixed" else config) * percent // 100
            for seed in design["random_seeds"]:
                replay = run_suite(events, prepared, tasks, entity="probe", models=models, builders=builders,
                                   mode=mode, cap=cap, seed=seed, adaptive=adaptive)
                for method in METHODS:
                    if seed != design["random_seeds"][0] and method != "B4":
                        continue
                    memory, stats = replay[method]
                    facts = {(f.predicate, f.value.casefold())
                             for f in memory.retrieve("probe", None, as_of=current)}
                    harmful = sum((pred, value.casefold()) in facts for pred, value in forbidden)
                    report.append({"history": history["id"], "mode": mode, "requested": percent,
                                   "method": method, "seed": seed, "reference_candidates": len(vectors),
                                   **stats, **assess(memory, "probe", current, expected, prepared),
                                   "harmful_current_adoptions": harmful})
    distribution["step23_fresh_development"] = summarize(new_vectors, full)
    result = {"design_sha256": sha(DESIGN), "dataset_sha256": sha(outcomes), "qwen": QWEN_DIGEST,
              "artifacts": manifest["artifacts_sha256"], "distribution": distribution,
              "provider_settings": SETTINGS, "verifier_prompt_schema": PROMPT_SCHEMA,
              "policy_reference_count": len(groups["train"]), "rows": report, "provider": provider.stats(),
              "wall_seconds": time.perf_counter() - started}
    write(output / "report.json", result)
    return {key: result[key] for key in ("distribution", "provider", "wall_seconds")}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("outcomes", type=Path)
    parser.add_argument("--nli", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.outcomes, args.nli, args.output), sort_keys=True))
