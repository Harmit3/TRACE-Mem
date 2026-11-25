"""Fit and score the frozen longitudinal V3 candidate stream in separate phases."""

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess

import numpy as np
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, confusion_matrix, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler

from trace_mem.controller import FEATURE_NAMES, LogisticController
from trace_mem.features_v3 import MINILM_REVISION, NLI_REVISION
from trace_mem.training import TrainingResult, _metrics, budget_threshold, load_model, save_model
from trace_mem.verification import select_random, select_ranked

SEED = 23
BUDGETS = (0, 10, 25, 50, 100)
GRID = (0.01, 0.1, 1.0, 10.0, 100.0)
BOOTSTRAPS = 2000
VARIANTS = {"full": tuple(range(8)), "no_nli": (0, 2, 3, 4, 5, 6, 7)}
PINNED = {
    "histories.jsonl": "d93d7e2ad0cf9dce8ca70d7bcb6ac0b0aeac2de7d6e3dc27218866ebb8c97c58",
    "pending-review.jsonl": "c170dbfe3c08eb17679677d7494200b7d5aa151665d743e2d11fdeb61ab9c5a1",
    "freeze.json": "6c714578c002a685e8df13f47b464d01d473d7c47ae14f8270de2798c8ac0b3c",
    "outcomes.jsonl": "837820ce735c3040d14ae1ace8cd24ef6ffc7c2986098e90ec95e0817fb81dc0",
    "features.jsonl": "401ebeb99582c7d78e31fe2ff529ee796fe58e05c0567847402024a2a9b93b38",
}
QWEN = "qwen2.5:7b-instruct-q4_K_M"
QWEN_DIGEST = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"


@dataclass(frozen=True)
class Candidate:
    family: str
    vector: tuple[float, ...]
    helpful: bool | None


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, content):
    with path.open("x", encoding="utf-8", newline="\n") as file:
        json.dump(content, file, indent=2, sort_keys=True, allow_nan=False)
        file.write("\n")


def provenance(dataset, release, projection):
    for name, directory in (
        ("histories.jsonl", dataset), ("pending-review.jsonl", dataset),
        ("freeze.json", release), ("outcomes.jsonl", release), ("features.jsonl", projection),
    ):
        if digest(directory / name) != PINNED[name]:
            raise ValueError(f"Frozen hash mismatch for {name}")
    freeze = json.loads((release / "freeze.json").read_bytes())
    verifier = freeze["verifier"]
    if (tuple(freeze["features"]) != FEATURE_NAMES or freeze["minilm"] != MINILM_REVISION
            or freeze["nli"] != NLI_REVISION or verifier["models"][QWEN] != QWEN_DIGEST
            or freeze["dataset"]["families"] != {"train": 20, "calibration": 10, "evaluation": 10}):
        raise ValueError("Incompatible feature, model or partition contract")
    return {"sha256": PINNED, "feature_code_sha256": freeze["code"]["trace_mem/features_v3.py"],
            "collection": {"minilm": freeze["minilm"], "nli": freeze["nli"], "verifier": verifier},
            "partition_families": freeze["dataset"]["families"]}


def read_partitions(path, splits):
    """Expose labels only for requested partitions; preserve chronology within each history."""
    rows = {split: [] for split in splits}
    unscored = Counter()
    families = {}
    for line in path.read_bytes().splitlines():
        history = json.loads(line)
        split = history["split"]
        family = history["family"]
        if families.setdefault(family, split) != split:
            raise ValueError("Scenario family crosses partitions")
        if split not in rows:
            continue
        for step in history["steps"]:
            for candidate in step["candidates"]:
                status = candidate["status"]
                if status != "verified":
                    if status in {"budget_exhausted", "verification_failure"}:
                        unscored[split] += 1
                    continue
                vector = tuple(candidate["features"])
                label = candidate["helpful"]
                if (len(vector) != len(FEATURE_NAMES) or not all(map(math.isfinite, vector))
                        or (label is not None and type(label) is not bool)):
                    raise ValueError("Invalid frozen feature vector or label")
                rows[split].append(Candidate(family, vector, label))
    return rows, dict(unscored)


def supervised(rows):
    known = [row for row in rows if row.helpful is not None]
    return (np.asarray([row.vector for row in known]),
            np.asarray([int(row.helpful) for row in known]),
            np.asarray([row.family for row in known]))


def fit_variant(train, calibration, folds, columns):
    x, y, _ = train
    calibration_x, calibration_y, _ = calibration
    x = x[:, columns]
    cv_ap = {}
    for c in GRID:
        predictions = np.empty(len(y))
        for fit, held in folds:
            scaler = StandardScaler().fit(x[fit])
            estimator = LogisticRegression(C=c, class_weight="balanced", random_state=SEED,
                                           max_iter=1000).fit(scaler.transform(x[fit]), y[fit])
            predictions[held] = estimator.decision_function(scaler.transform(x[held]))
        cv_ap[c] = float(average_precision_score(y, predictions))
    best = max(GRID, key=cv_ap.get)
    scaler = StandardScaler().fit(x)
    estimator = LogisticRegression(C=best, class_weight="balanced", random_state=SEED,
                                   max_iter=1000).fit(scaler.transform(x), y)
    logits = estimator.decision_function(scaler.transform(calibration_x[:, columns]))
    fitted = LogisticRegression(C=1.0, random_state=SEED, max_iter=1000).fit(
        logits[:, None], calibration_y)
    candidate_slope = float(fitted.coef_[0, 0])
    slope, offset = ((candidate_slope, float(fitted.intercept_[0]))
                     if candidate_slope > 0 else (1.0, 0.0))

    means = np.zeros(len(FEATURE_NAMES))
    scales = np.ones(len(FEATURE_NAMES))
    weights = np.zeros(len(FEATURE_NAMES))
    means[list(columns)] = scaler.mean_
    scales[list(columns)] = scaler.scale_
    weights[list(columns)] = estimator.coef_[0] * slope
    controller = LogisticController(tuple(means), tuple(scales), tuple(weights),
                                    float(estimator.intercept_[0]) * slope + offset)
    return controller, {
        "fit_features": [FEATURE_NAMES[i] for i in columns], "C": best,
        "cv_pooled_average_precision": {str(c): score for c, score in cv_ap.items()},
        "constant_training_features": [FEATURE_NAMES[i] for i, var in zip(columns, scaler.var_) if var == 0],
        "raw_weights": estimator.coef_[0].tolist(), "raw_intercept": float(estimator.intercept_[0]),
        "calibrator": {"C": 1.0, "fitted_slope": candidate_slope, "applied_slope": slope,
                       "applied_offset": offset, "identity_fallback": candidate_slope <= 0},
    }


def score_stream(rows, controllers, prevalence):
    def bounded(x):
        return min(x, math.nextafter(1.0, 0.0))

    return {
        **{key: [model.score(row.vector) for row in rows] for key, model in controllers.items()},
        "intercept": [prevalence for row in rows],
        "b5_uncertainty": [bounded(row.vector[6]) for row in rows],
        "contradiction": [bounded(row.vector[1]) for row in rows],
    }


def fit(path, output, source):
    partitions, _ = read_partitions(path, {"train", "calibration"})
    train = supervised(partitions["train"])
    calibration = supervised(partitions["calibration"])
    if any(set(split[1]) != {0, 1} for split in (train, calibration)):
        raise ValueError("Both fit partitions need both established label classes")
    x, y, groups = train
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    folds = list(splitter.split(x, y, groups))
    if any(set(groups[a]) & set(groups[b]) or set(y[a]) != {0, 1} for a, b in folds):
        raise ValueError("Grouped CV has overlapping families or a single-class fit fold")
    output.mkdir(parents=True, exist_ok=False)
    models, diagnostics = {}, {}
    for key, columns in VARIANTS.items():
        models[key], diagnostics[key] = fit_variant(train, calibration, folds, columns)
    prevalence = float(np.mean(y))
    scores = score_stream(partitions["calibration"], models, prevalence)
    thresholds = {
        key: {str(p): budget_threshold(values, p / 100) for p in BUDGETS}
        for key, values in scores.items()
    }
    base = {
        "source": source, "seed": SEED, "python": platform.python_version(),
        "numpy": np.__version__, "sklearn": sklearn.__version__,
        "script_sha256": digest(Path(__file__)),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "class_weight": "balanced", "cv_folds": len(folds), "classification_threshold": 0.5,
        "selection_metric": "pooled out-of-fold average precision",
        "intercept_prevalence": prevalence,
        "fit_counts": {"train": [len(y), int(sum(y))],
                       "calibration": [len(calibration[1]), int(sum(calibration[1]))]},
        "thresholds": thresholds, "budget_percentages": BUDGETS,
        "bootstrap_replicates": BOOTSTRAPS,
    }
    paths = {}
    for key, model in models.items():
        model_path = output / f"{key}.json"
        save_model(TrainingResult(model, thresholds[key]["25"], {**base, **diagnostics[key]}), model_path)
        if load_model(model_path).controller != model:
            raise ValueError("Exported artifact does not round-trip through deployed loader")
        paths[model_path.name] = digest(model_path)
    write_json(output / "fit-freeze.json", {**base, "artifacts_sha256": paths})


def classification(labels, scores):
    result = _metrics([int(label) for label in labels], [float(score) for score in scores], 0.5)
    tn, fp, fn, tp = confusion_matrix(labels, np.asarray(scores) >= 0.5, labels=[0, 1]).ravel()
    both = bool((tp + fn) and (tn + fp))
    result.update({
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
        "balanced_accuracy": float((tp / (tp + fn) + tn / (tn + fp)) / 2) if both else None,
        "auroc": float(roc_auc_score(labels, scores)) if both else None,
        "average_precision": float(average_precision_score(labels, scores)) if both else None,
    })
    return result


def allocation(rows, scores, thresholds, unscored):
    def summarize(indices, percent):
        labels = [rows[i].helpful for i in indices]
        return {"requested_percent": percent, "calls": len(indices),
                "coverage_scored": len(indices) / len(rows),
                "coverage_all_eligible": len(indices) / (len(rows) + unscored),
                "helpful": labels.count(True), "not_helpful": labels.count(False),
                "pending": labels.count(None)}

    ranked = {}
    for key, values in {**scores, "b4_random": None}.items():
        ranked[key] = {}
        for p in BUDGETS:
            count = len(rows) * p // 100
            chosen = (select_random(len(rows), count, seed=SEED) if values is None
                      else select_ranked(values, count))
            ranked[key][str(p)] = summarize(chosen, p)
    transferred = {
        key: {str(p): summarize([i for i, score in enumerate(values)
                                 if score >= thresholds[key][str(p)]], p) for p in BUDGETS}
        for key, values in scores.items()
    }
    return {"rank_matched": ranked, "calibration_threshold_transfer_uncapped": transferred}


def intervals(labels, scores, groups):
    rng = np.random.default_rng(SEED)
    families = [np.flatnonzero(groups == group) for group in np.unique(groups)]
    samples = {key: [] for key in (
        "full_auroc", "full_average_precision", "full_brier", "no_nli_auroc",
        "no_nli_average_precision", "no_nli_brier", "full_minus_no_nli_average_precision",
        "full_minus_no_nli_auroc", "full_minus_no_nli_brier",
    )}
    for _ in range(BOOTSTRAPS):
        which = rng.integers(len(families), size=len(families))
        indices = np.concatenate([families[i] for i in which])
        y = labels[indices]
        full, no_nli = (np.asarray(scores[key])[indices] for key in VARIANTS)
        for name, left, right in (
            ("brier", np.mean((full - y) ** 2), np.mean((no_nli - y) ** 2)),
            *((("auroc", roc_auc_score(y, full), roc_auc_score(y, no_nli)),
               ("average_precision", average_precision_score(y, full), average_precision_score(y, no_nli)))
              if len(np.unique(y)) == 2 else ()),
        ):
            samples[f"full_{name}"].append(left)
            samples[f"no_nli_{name}"].append(right)
            samples[f"full_minus_no_nli_{name}"].append(left - right)
    return {key: {"low": float(np.quantile(values, 0.025)) if values else None,
                  "high": float(np.quantile(values, 0.975)) if values else None,
                  "valid_replicates": len(values)} for key, values in samples.items()}


def plots(directory, labels, scores, metrics, budgets):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "trace-mem-v3-t1"
    import matplotlib.pyplot as plt
    from sklearn.metrics import precision_recall_curve

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(directory / f"{name}.svg", metadata={"Date": None})
        plt.close(fig)

    fig, ax = plt.subplots()
    for key, values in scores.items():
        precision, recall, _ = precision_recall_curve(labels, values)
        ax.step(recall, precision, where="post", label=key)
    ax.set(xlabel="Recall", ylabel="Precision", title="Independent V3 precisionâ€“recall")
    ax.legend()
    save(fig, "precision-recall")

    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], "--", color="gray")
    for key in (*VARIANTS, "intercept"):
        bins = metrics[key]["calibration_bins"]
        ax.plot([b["mean_probability"] for b in bins],
                [b["positive_fraction"] for b in bins], ".-", label=key)
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Mean score in bin",
           ylabel="Observed helpfulness", title=f"Exploratory reliability ({len(labels)} labeled candidates)")
    ax.legend()
    save(fig, "reliability")

    fig, axes = plt.subplots(1, 2, figsize=(8, 4))
    for key, ax in zip(VARIANTS, axes):
        matrix = np.asarray(metrics[key]["confusion_matrix"])
        ax.imshow(matrix, cmap="Blues", vmin=0, vmax=len(labels))
        for (i, j), value in np.ndenumerate(matrix):
            ax.text(j, i, str(value), ha="center", va="center")
        ax.set(xticks=[0, 1], yticks=[0, 1], xlabel="Predicted", ylabel="Established gold", title=key)
    save(fig, "confusion")

    fig, ax = plt.subplots()
    for key, series in budgets["rank_matched"].items():
        ax.plot(BUDGETS, [series[str(p)]["helpful"] for p in BUDGETS], ".-", label=key)
    ax.set(xlabel="Requested coverage (%)", ylabel="Known helpful candidates selected",
           title="Fixed-stream verification allocation")
    ax.legend()
    save(fig, "budget-allocation")


def evaluate(path, frozen, output, source):
    manifest = json.loads((frozen / "fit-freeze.json").read_bytes())
    if (manifest["source"] != source or manifest["script_sha256"] != digest(Path(__file__))
            or set(manifest["artifacts_sha256"]) != {f"{key}.json" for key in VARIANTS}
            or any(digest(frozen / name) != expected
                   for name, expected in manifest["artifacts_sha256"].items())):
        raise ValueError("Fit freeze, artifact or source hash mismatch")
    artifacts = {key: load_model(frozen / f"{key}.json") for key in VARIANTS}
    models = {key: artifact.controller for key, artifact in artifacts.items()}
    partitions, unscored = read_partitions(path, {"evaluation"})
    rows = partitions["evaluation"]
    scores = score_stream(rows, models, manifest["intercept_prevalence"])
    known = [i for i, row in enumerate(rows) if row.helpful is not None]
    _, labels, groups = supervised(rows)
    labeled_scores = {key: [values[i] for i in known] for key, values in scores.items()}
    metrics = {key: classification(labels, values) for key, values in labeled_scores.items()}
    raw_brier = {}
    for key, artifact in artifacts.items():
        model, report = artifact.controller, artifact.report
        weights = [0.0] * len(FEATURE_NAMES)
        for column, weight in zip(VARIANTS[key], report["raw_weights"]):
            weights[column] = weight
        raw = LogisticController(model.means, model.scales, tuple(weights), report["raw_intercept"])
        raw_brier[key] = float(np.mean((np.asarray([raw.score(rows[i].vector) for i in known])
                                       - labels) ** 2))
    budgets = allocation(rows, scores, manifest["thresholds"], unscored.get("evaluation", 0))
    results = {
        "fit_freeze_sha256": digest(frozen / "fit-freeze.json"),
        "classification": metrics, "allocation": budgets, "raw_logistic_brier": raw_brier,
        "family_bootstrap_95pct": intervals(labels, labeled_scores, groups),
        "family_bootstrap_replicates": BOOTSTRAPS, "seed": SEED,
        "labeled_families": len(set(groups)), "positive_families": len(set(groups[labels == 1])),
        "scored_candidates": len(rows), "scored_pending_gold": len(rows) - len(labels),
        "unscored_eligible": unscored.get("evaluation", 0),
    }
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "evaluation.json", results)
    plots(output, labels, labeled_scores, metrics, budgets)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("fit", "evaluate"))
    parser.add_argument("dataset", type=Path)
    parser.add_argument("release", type=Path)
    parser.add_argument("projection", type=Path)
    parser.add_argument("frozen", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source = provenance(args.dataset, args.release, args.projection)
    path = args.release / "outcomes.jsonl"
    if args.phase == "fit":
        fit(path, args.frozen, source)
    elif args.output is not None:
        evaluate(path, args.frozen, args.output, source)
    else:
        parser.error("evaluate requires --output")


if __name__ == "__main__":
    main()
