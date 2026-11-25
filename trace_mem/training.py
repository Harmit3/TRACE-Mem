"""Collect independent decisions and fit, calibrate, and save a T1 controller."""

import argparse
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import date
import json
import math
from pathlib import Path
from typing import Literal

from trace_mem.claims import Claim
from trace_mem.controller import FEATURE_NAMES, LogisticController, features_for
from trace_mem.data.updateset import add_records, helpfulness, read_release, write_release
from trace_mem.memory import Fact, Source
from trace_mem.semantic import SemanticEvidence


@dataclass(frozen=True, slots=True)
class DecisionInput:
    old: Fact
    new: Claim
    source: Source
    conversation: tuple[str, ...]


DecisionPolicy = Callable[[DecisionInput], dict]


def eligible_case(case: DecisionInput) -> bool:
    return (case.new.intent != "delete" and case.old.predicate == case.new.predicate
            and case.old.value.casefold() != case.new.value.casefold()
            and case.new.effective_on > case.old.valid_from
            and case.old.visible_on(case.new.effective_on))


def _inputs(row: dict) -> DecisionInput:
    old, new = row["old_fact"], row["new_claim"]
    old_source = Source(date.fromisoformat(old["observed_on"]), old["source_ref"])
    source = Source(date.fromisoformat(new["observed_on"]), new["source_ref"])
    fact = Fact(old["fact_id"], row["persona_id"], old["predicate"], old["value"],
                old_source, date.fromisoformat(old["valid_from"]),
                date.fromisoformat(old["valid_to"]) if old["valid_to"] else None)
    claim = Claim(new["predicate"], new["value"], new["intent"],
                  date.fromisoformat(new["effective_on"]),
                  date.fromisoformat(new["expires_on"]) if new["expires_on"] else None)
    return DecisionInput(fact, claim, source, tuple(turn["text"] for turn in row["conversation"]))


def collect_pairs(
    dataset: Path,
    output: Path,
    *,
    unverified: DecisionPolicy,
    verified: DecisionPolicy,
    reference: str,
    origin: Literal["recorded_verifier", "synthetic_mock"],
    eligible_only: bool = False,
) -> dict:
    """Collect train/validation outcomes from the same immutable, gold-free inputs."""
    if origin not in ("recorded_verifier", "synthetic_mock") or not reference.strip():
        raise ValueError("Explicit outcome origin and run reference are required")
    if output.exists():
        raise FileExistsError(output)
    rows, manifest = read_release(dataset)
    records = []
    for row in rows:
        if row["split"] == "test" or row["outcomes"] is not None:
            continue
        case = _inputs(row)
        if eligible_only and not eligible_case(case):
            continue
        before = dict(unverified(case))
        after = dict(verified(case))
        records.append({"case_id": row["case_id"], "outcomes": {
            "origin": origin, "reference": reference, "unverified": before, "verified": after,
        }})
    updated = add_records(rows, records, field="outcomes")
    return write_release(output, updated, lineage={
        "operation": "collect-pairs", "parent_cases_sha256": manifest["files"]["cases.jsonl"],
        "origin": origin, "reference": reference,
    }, **manifest["settings"])


@dataclass(frozen=True, slots=True)
class TrainingResult:
    controller: LogisticController
    threshold: float
    report: dict


def budget_threshold(scores: Sequence[float], target_fraction: float) -> float:
    """Spend as much of the validation cap as possible with a single threshold."""
    if not math.isfinite(target_fraction) or not 0 <= target_fraction <= 1:
        raise ValueError("Target fraction must be between zero and one")
    if any(not math.isfinite(score) or not 0 <= score < 1 for score in scores):
        raise ValueError("Scores must be finite probabilities below one")
    cap = math.floor(len(scores) * target_fraction)
    threshold = 1.0
    used = 0
    counts = Counter(scores)
    for score in sorted(counts, reverse=True):
        used += counts[score]
        if used > cap:
            break
        threshold = score
    return threshold


def _metrics(labels: list[int], scores: list[float], threshold: float) -> dict:
    from sklearn.metrics import accuracy_score, brier_score_loss, precision_recall_fscore_support

    predictions = [score >= threshold for score in scores]
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, predictions, average="binary", zero_division=0,
    )
    bins = []
    for index in range(10):
        members = [(label, score) for label, score in zip(labels, scores)
                   if min(int(score * 10), 9) == index]
        if members:
            bins.append({
                "lower": index / 10, "upper": (index + 1) / 10, "count": len(members),
                "mean_probability": sum(score for _, score in members) / len(members),
                "positive_fraction": sum(label for label, _ in members) / len(members),
            })
    ece = sum(b["count"] / len(labels) * abs(b["mean_probability"] - b["positive_fraction"])
              for b in bins)
    return {
        "rows": len(labels), "positives": sum(labels), "selected": sum(predictions),
        "accuracy": accuracy_score(labels, predictions), "precision": float(precision),
        "recall": float(recall), "f1": float(f1), "brier": brier_score_loss(labels, scores),
        "ece_10_bins": ece, "calibration_bins": bins,
    }


def train(
    dataset: Path,
    *,
    target_fraction: float,
    seed: int,
    allow_mock: bool = False,
    semantic: SemanticEvidence | None = None,
    semantic_reference: str | None = None,
) -> TrainingResult:
    """Fit on train, then calibrate and choose a cutoff on validation only."""
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("Seed must be an unsigned 32-bit integer")
    if not math.isfinite(target_fraction) or not 0 <= target_fraction <= 1:
        raise ValueError("Target fraction must be between zero and one")
    if (semantic is None) != (semantic_reference is None) or semantic_reference == "":
        raise ValueError("Provide a feature provider and its reference together")
    rows, manifest = read_release(dataset)
    inputs: dict[str, list[DecisionInput]] = {"train": [], "validation": []}
    labels: dict[str, list[int]] = {"train": [], "validation": []}
    origins = Counter()
    for row in rows:
        split = row["split"]
        if split not in inputs or row["new_claim"]["intent"] == "delete":
            continue
        label = helpfulness(row["gold"], row["outcomes"])
        if label is None:
            continue
        origin = row["outcomes"]["origin"]
        if origin == "synthetic_mock" and not allow_mock:
            continue
        case = _inputs(row)
        # Match live T1's single-target conflict boundary.
        if not eligible_case(case):
            continue
        inputs[split].append(case)
        labels[split].append(int(label))
        origins[origin] += 1
    for split, split_labels in labels.items():
        if set(split_labels) != {0, 1}:
            raise ValueError(f"{split} requires eligible positive and negative helpfulness labels")

    import sklearn
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    vectors = {split: [features_for(case.new, case.old, entity=case.old.entity,
                                   source=case.source, budget_remaining_fraction=1.0,
                                   semantic=semantic) for case in cases]
               for split, cases in inputs.items()}
    scaler = StandardScaler().fit(vectors["train"])
    model = LogisticRegression(random_state=seed, solver="lbfgs", max_iter=1000)
    model.fit(scaler.transform(vectors["train"]), labels["train"])
    validation_logits = model.decision_function(scaler.transform(vectors["validation"]))
    calibrator = LogisticRegression(random_state=seed, solver="lbfgs", max_iter=1000)
    calibrator.fit(validation_logits.reshape(-1, 1), labels["validation"])
    slope = float(calibrator.coef_[0, 0])
    controller = LogisticController(
        tuple(map(float, scaler.mean_)), tuple(map(float, scaler.scale_)),
        tuple(float(weight) * slope for weight in model.coef_[0]),
        float(model.intercept_[0]) * slope + float(calibrator.intercept_[0]),
    )
    scores = [controller.score(row) for row in vectors["validation"]]
    threshold = budget_threshold(scores, target_fraction)
    report = {
        "dataset_sha256": manifest["files"]["cases.jsonl"],
        "sklearn_version": sklearn.__version__, "seed": seed,
        "feature_provider": semantic_reference if semantic is not None else "rule-proxies",
        "budget_feature": 1.0, "target_fraction": target_fraction,
        "outcome_origins": dict(origins),
        "contains_mock_outcomes": origins["synthetic_mock"] > 0,
        "training_rows": len(labels["train"]),
        "validation": _metrics(labels["validation"], scores, threshold),
    }
    return TrainingResult(controller, threshold, report)


def save_model(result: TrainingResult, path: Path) -> None:
    artifact = {
        "version": 1, "features": FEATURE_NAMES, "controller": asdict(result.controller),
        "threshold": result.threshold, "report": result.report,
    }
    with path.open("x", encoding="utf-8", newline="\n") as file:
        json.dump(artifact, file, sort_keys=True, allow_nan=False)
        file.write("\n")


def load_model(path: Path) -> TrainingResult:
    artifact = json.loads(path.read_text(encoding="utf-8"))
    if artifact["version"] != 1 or tuple(artifact["features"]) != FEATURE_NAMES:
        raise ValueError("Unsupported T1 artifact version or feature order")
    parameters = artifact["controller"]
    controller = LogisticController(tuple(parameters["means"]), tuple(parameters["scales"]),
                                    tuple(parameters["weights"]), parameters["intercept"])
    threshold = artifact["threshold"]
    if len(controller.weights) != len(FEATURE_NAMES) or not 0 <= threshold <= 1:
        raise ValueError("Invalid T1 model width or threshold")
    return TrainingResult(controller, threshold, artifact["report"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("--target-fraction", type=float, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--allow-mock", action="store_true")
    args = parser.parse_args()
    try:
        result = train(args.dataset, target_fraction=args.target_fraction, seed=args.seed,
                       allow_mock=args.allow_mock)
        save_model(result, args.model)
        print(json.dumps(result.report, sort_keys=True))
    except (ValueError, OSError, ImportError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
