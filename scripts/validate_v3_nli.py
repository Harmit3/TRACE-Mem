"""Validate pinned local NLI and backfill v3 scores from pre-verification evidence."""

import argparse
from collections import Counter
from contextlib import closing
from datetime import date
import json
from pathlib import Path
import sqlite3
from statistics import correlation, median, pvariance
import time

from scripts.compare_local_verifiers import MODE, QWEN, SETTINGS, freeze, local_json
from scripts.updateset_v2_pilot import PROMPT_SCHEMA, QWEN_DIGEST
from trace_mem.baselines import PreparedClaim, _apply, _eligible_target
from trace_mem.claims import Claim, EXTRACTION_PROMPT
from trace_mem.controller import FEATURE_NAMES
from trace_mem.data.memora import Event
from trace_mem.data.updateset_v2 import canonical, rows_bytes, sha
from trace_mem.data.updateset_v3 import cases
from trace_mem.features_v3 import CachedMiniLM, NLI_REVISION, V3Features, pinned_nli
from trace_mem.llm_tasks import LLMTasks
from trace_mem.memory import Fact, Source, TemporalMemory
from trace_mem.providers import ChatProvider, ProviderConfig, ProviderError


PILOT_HASH = "a88d4bdb52a1521fe982d401147dd98d52cf56fade077dd476b6ff278fe9ccb1"
# Independent natural-language pairs. Labels describe logical compatibility,
# not whether a memory write should be authorized by the verifier.
CASES = (
    ("contradiction", "Mara's only current employer is Elm Books.", "Mara's only current employer is Stone Books."),
    ("contradiction", "Tariq lives at Cedar House as of April 2.", "On April 2 Tariq does not live at Cedar House."),
    ("contradiction", "Leah's assignment to Night Shift was canceled before it began.", "Leah started her assignment to Night Shift."),
    ("contradiction", "Dara uses email as her only contact method.", "Dara uses only telephone calls for contact."),
    ("contradiction", "Since May, Casey's residence has been Maple Row and nowhere else.", "After May, Casey lives exclusively at Olive Court."),
    ("contradiction", "Nico never worked for West Bakery.", "Nico worked for West Bakery last winter."),
    ("contradiction", "As of noon the old Gold Plan was canceled.", "At noon the old Gold Plan remained active."),
    ("contradiction", "On June 10 the assigned desk was number nine.", "On June 10 the assigned desk was not number nine."),
    ("entailment", "Inez's current home is Birch Mews.", "Inez currently lives at Birch Mews."),
    ("entailment", "Omar switched from North Garage to Harbor Garage and started work there yesterday.", "Omar has started working at Harbor Garage."),
    ("entailment", "Drift Lodge is just another name for the same building known as Shore Lodge.", "Drift Lodge and Shore Lodge refer to the same building."),
    ("entailment", "Ravi first began working at Moss Lab in July.", "Ravi started working at Moss Lab in July."),
    ("entailment", "Tess left her role at Pine Theater on Tuesday.", "Tess used to work at Pine Theater."),
    ("entailment", "The lease renewal confirms that Ren still lives at Park Gate.", "Ren's residence remains Park Gate."),
    ("entailment", "Jules may accept the offer but has not made a decision.", "Jules has not decided whether to accept the offer."),
    ("entailment", "Ari only visited Opal Inn for a weekend.", "Ari went to Opal Inn."),
    ("neutral", "In March, Sam worked for Ridge Lab.", "In July, Sam worked for Brook Lab."),
    ("neutral", "Ava might move to North Wharf next year.", "Ava currently lives at East Wharf."),
    ("neutral", "Sol managed the Aurora program last year.", "Sol has an evening class on Wednesday."),
    ("neutral", "The transfer to Flint Depot is being discussed.", "Flint Depot hired the worker."),
    ("neutral", "West Hill is Lila's current address.", "Lila visited Cedar Hotel last Friday."),
    ("neutral", "Pia's brother started working at Orchard Farm.", "Pia works at Reed Farm."),
    ("neutral", "A draft form names Union Clinic without confirming the new placement.", "Union Clinic is Mira's confirmed employer."),
    ("neutral", "Lou's subscription was active on April 7.", "Lou's subscription expired on May 12."),
)


class ExtractionTape:
    """Read only original extraction entries. This adapter has no network transport."""

    def __init__(self, connection):
        self.connection = connection
        self.settings = ProviderConfig("ollama", QWEN, 48, **SETTINGS)

    def generate(self, task, system, payload, validate):
        if task != "extract-v1" or system != EXTRACTION_PROMPT:
            raise ValueError("Only frozen extraction responses can be read")
        url, _, body = ChatProvider.request_for(self.settings, task, system, payload)
        key = ChatProvider.cache_key(task, url, body)
        entry = self.connection.execute("SELECT text FROM response WHERE key=?", (key,)).fetchone()
        if entry is None:
            raise ValueError("Frozen extraction response is missing")
        validate(entry[0])
        return entry[0]


def reconstruct(case: dict, tasks: LLMTasks):
    observed = date.fromisoformat(case["observed_on"])
    prior = case["old"]
    old_day = date.fromisoformat(prior["observed_on"])
    entity = case["id"] + "/person"
    original = Fact(case["id"] + "/prior", entity, prior["predicate"], prior["value"],
                    Source(old_day, "prior", prior["kind"]), old_day)
    transcript = case["transcript"]
    claims = tasks.extract(Event(observed, 2, len(transcript), "user",
                                 transcript[-1]["text"], case["kind"]))
    prefix = TemporalMemory()
    prefix.accept(original)
    source = Source(observed, "focal", case["kind"])
    for index, claim in enumerate(claims):
        target = _eligible_target(prefix, entity, claim)
        if target is not None and target.fact_id == original.fact_id:
            return claim, target, source
        item = PreparedClaim(claim, source, f"candidate/{index}")
        _apply(prefix, entity, item.claim, item.source, item.fact_id, "B2", None, None, None)
    raise ValueError("Recorded candidate cannot be reconstructed")


def feature_audit(rows: list[dict]) -> dict:
    columns = dict(zip(FEATURE_NAMES, zip(*(row["features"] for row in rows))))
    varying = {name: values for name, values in columns.items() if len(set(values)) > 1}
    return {
        "rows": len(rows), "unique_vectors": len({tuple(row["features"]) for row in rows}),
        "features": {name: {"distinct": len(set(values)), "min": min(values), "max": max(values),
                            "missing": values.count(None), "variance": pvariance(values)}
                     for name, values in columns.items()},
        "pearson_nonconstant": {
            f"{name}:{other}": correlation(values, right)
            for i, (name, values) in enumerate(varying.items())
            for other, right in list(varying.items())[i + 1:]
        },
    }


def run(model_dir: Path, original_dir: Path, output: Path) -> dict:
    import psutil
    import torch
    import transformers

    identity = freeze(QWEN_DIGEST)
    if identity["prompt_schema_sha256"] != PROMPT_SCHEMA:
        raise ValueError("Frozen verifier changed")
    original = (original_dir / "outcomes.jsonl").read_bytes()
    if sha(original) != PILOT_HASH:
        raise ValueError("Original v3 pilot does not match its published hash")
    output.mkdir(parents=True, exist_ok=False)
    metadata = {
        "version": "v3-nli-diagnostic-1", "source_outcomes_sha256": PILOT_HASH,
        "cases_sha256": sha(rows_bytes(CASES)), "nli_revision": NLI_REVISION,
        "threads": 4, "device": "cpu", "torch": torch.__version__,
        "transformers": transformers.__version__,
        "gate": {"min_accuracy": 0.75, "min_contradiction_recall": 0.75,
                 "max_failure": 0, "min_other_class_recall": 0.5},
    }
    (output / "freeze.json").write_bytes(canonical(metadata))
    torch.set_num_threads(4)
    process = psutil.Process()
    rss = {"before_models": process.memory_info().rss}
    infer = pinned_nli(model_dir)
    rss["with_nli_loaded"] = process.memory_info().rss
    counters = Counter()
    scores = {}
    timings = []
    details = []
    failures = 0
    for expected, premise, hypothesis in CASES:
        started = time.perf_counter()
        try:
            result = infer(premise, hypothesis)
        except (RuntimeError, ValueError):
            failures += 1
            counters[f"{expected}->failure"] += 1
            details.append({"expected": expected, "prediction": None, "contradiction": None})
            continue
        timings.append((time.perf_counter() - started) * 1000)
        counters[f"{expected}->{result.label}"] += 1
        scores.setdefault(expected, []).append(result.contradiction)
        details.append({"expected": expected, "prediction": result.label,
                        "contradiction": result.contradiction})
    classes = ("contradiction", "entailment", "neutral")
    recall = {label: counters[f"{label}->{label}"] / sum(row[0] == label for row in CASES)
              for label in classes}
    accuracy = sum(counters[f"{label}->{label}"] for label in classes) / len(CASES)
    rss["after_nli_validation"] = process.memory_info().rss
    builder = V3Features(CachedMiniLM(), infer)
    rss["with_both_cpu_models"] = process.memory_info().rss
    indexed = {case["id"]: case for case in cases()}
    new_rows = []
    with closing(sqlite3.connect((original_dir / "responses.sqlite").resolve().as_uri() + "?mode=ro",
                                 uri=True)) as db:
        tasks = LLMTasks(ExtractionTape(db))
        for row in map(json.loads, original.splitlines()):
            if "features" not in row:
                continue
            original_vector = row["features"]
            if original_vector[1] is not None:
                raise ValueError("Expected deliberately missing NLI score in original")
            claim, target, source = reconstruct(indexed[row["id"]], tasks)
            vector = builder(claim, target, entity=target.entity, source=source,
                             budget_remaining_fraction=original_vector[-1])
            if any(abs(value - original_vector[i]) > 1e-6 for i, value in enumerate(vector) if i != 1):
                raise ValueError("Recorded pre-verification covariates could not be reproduced")
            features = list(original_vector)
            features[1] = vector[1]
            new_rows.append({"id": row["id"], "split": row["split"], "family": row["family"],
                             "features": features})
    data = rows_bytes(new_rows)
    (output / "features.jsonl").write_bytes(data)
    available_before = psutil.virtual_memory().available
    local = ChatProvider(ProviderConfig("ollama", QWEN, 1, **SETTINGS), output / "coexistence.sqlite")
    real = LLMTasks(local, verification_mode=MODE)
    day = date(2026, 6, 4)
    source = Source(day, "smoke")
    claim = Claim("job", "Summer Studio", "uncertain", day)
    target = Fact("smoke-fact", "smoke-person", "job", "Winter Studio",
                  Source(date(2026, 6, 1), "smoke-prior"), date(2026, 6, 1))
    try:
        qwen_verdict = real.verify(claim, target, conversation=(
            "user: I interviewed at Summer Studio, but Winter Studio still employs me.",))
    except ProviderError:
        qwen_verdict = None
    builder(claim, target, entity=target.entity, source=source, budget_remaining_fraction=1.0)
    resident = [dict(name=x["name"], size=x["size"], size_vram=x["size_vram"],
                     context_length=x["context_length"])
                for x in local_json("/api/ps")["models"] if x["name"] == QWEN]
    rss["after_combined_smoke"] = process.memory_info().rss
    report = metadata | {
        "validation": {"accuracy": accuracy, "recall": recall, "confusion": dict(counters),
                       "failures": failures,
                       "passed": accuracy >= 0.75 and recall["contradiction"] >= 0.75
                       and min(recall["neutral"], recall["entailment"]) >= 0.5 and failures == 0,
                       "contradiction_scores": {label: {"min": min(values), "median": median(values),
                                                       "max": max(values)}
                                                for label, values in scores.items()},
                       "mean_ms": sum(timings) / len(timings) if timings else None,
                       "median_ms": median(timings) if timings else None,
                       "max_ms": max(timings, default=None), "details": details},
        "diagnostic_features_sha256": sha(data), "feature_audit": feature_audit(new_rows),
        "rss_bytes": rss, "coexistence": {"qwen": resident, "verdict": qwen_verdict,
                                          "usage": local.stats(), "available_before": available_before,
                                          "available_after": psutil.virtual_memory().available},
    }
    if sha((original_dir / "outcomes.jsonl").read_bytes()) != PILOT_HASH:
        raise ValueError("Original pilot changed during the diagnostic")
    (output / "report.json").write_bytes(canonical(report) + b"\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("model_dir", "original_dir", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if Path("results").resolve() not in args.output.resolve().parents:
        parser.error("Use an ignored directory under results/")
    print(json.dumps(run(args.model_dir, args.original_dir, args.output), sort_keys=True))
