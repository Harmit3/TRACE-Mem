"""Aggregate frozen Step 30 checkpoints and publish only summary statistics."""

from argparse import ArgumentParser
from collections import defaultdict
from pathlib import Path
from statistics import fmean
import json
import random

import numpy as np


def paired_interval(families, replicates, seed):
    means = [fmean(values) for values in families.values()]
    rng = random.Random(seed)
    draws = [fmean(rng.choices(means, k=len(means))) for _ in range(replicates)]
    lower, upper = np.quantile(draws, (0.025, 0.975))
    return {"difference": fmean(means), "lower": float(lower), "upper": float(upper),
            "families": len(means)}


SUMS = ("current", "current_total", "historical", "historical_total", "deletion",
        "deletion_total", "authorized_deletion", "harmful_adoptions", "helpful_verifications",
        "harmful_verifications", "eligible_candidates", "reference_candidates",
        "verification_attempts", "verification_failures", "budget_cap", "stale_targets")
METHODS = ("B0", "B1", "B2", "B3", "B4", "B5", "T1", "T1-no-NLI", "T2", "H-paced")


def summarize(report, config):
    grouped = defaultdict(list)
    paired = defaultdict(dict)
    stochastic = defaultdict(list)
    oracle_rows = []
    expected_rows = {
        (mode, budget, method, seed)
        for mode in ("fixed", "closed-loop")
        for budget in config["budget_percents"]
        for method in METHODS
        for seed in (config["seeds"] if method == "B4" else config["seeds"][:1])
    }
    identities = set()
    for history in report["histories"]:
        observed = {(r["mode"], r["budget"], r["method"], r["seed"]) for r in history["rows"]}
        if (history["history"] in identities or len(history["rows"]) != len(expected_rows)
                or observed != expected_rows):
            raise ValueError("Missing or duplicate frozen policy conditions")
        identities.add(history["history"])
        by_condition = defaultdict(list)
        for row in history["rows"]:
            if (not 0 <= row["verification_attempts"] <= row["budget_cap"]
                    or row["mode"] == "fixed" and row["verification_attempts"] != row["budget_cap"]
                    or row["authorized_deletion"] != row["deletion_total"]):
                raise ValueError("An evaluation row failed budget or evidence checks")
            by_condition[row["mode"], row["budget"], row["method"]].append(row)
            if row["method"] == "B4":
                stochastic[row["mode"], row["budget"], row["seed"]].append(row)
        for key, repetitions in by_condition.items():
            row = {metric: fmean(r[metric] for r in repetitions) for metric in SUMS}
            row["seeds"] = len(repetitions)
            readings = [r["qa"] for r in repetitions if "qa" in r]
            row["qa"] = score_readings(readings)
            grouped[key].append(row)
            paired[key][history["history"]] = (history["family"], row["current"] / row["current_total"])
        oracle_rows.append(history["oracle"] | {"qa": score_readings(
            [history["oracle_qa"]] if "oracle_qa" in history else [])})
    rows = []
    for (mode, budget, method), histories in sorted(grouped.items()):
        row = {metric: sum(h[metric] for h in histories) for metric in SUMS}
        row.update(mode=mode, budget=budget, method=method, histories=len(histories),
                   seeds=min(h["seeds"] for h in histories), qa=combine_readings(histories))
        row["current_accuracy"] = row["current"] / row["current_total"]
        row["historical_accuracy"] = row["historical"] / row["historical_total"]
        row["achieved_reference_coverage"] = row["verification_attempts"] / row["reference_candidates"]
        row["budget_utilization"] = (row["verification_attempts"] / row["budget_cap"]
                                     if row["budget_cap"] else None)
        rows.append(row)
    contrasts = []
    for mode in ("fixed", "closed-loop"):
        for budget in config["budget_percents"]:
            for left, right in (("T2", "H-paced"), ("T1", "T1-no-NLI"), ("T2", "B4"), ("T1", "B5")):
                first, second = paired[mode, budget, left], paired[mode, budget, right]
                families = defaultdict(list)
                for identity, (family, value) in first.items():
                    if identity in second:
                        families[family].append(value - second[identity][1])
                if families:
                    contrasts.append(dict(mode=mode, budget=budget, left=left, right=right,
                                          histories=sum(map(len, families.values())),
                                          **paired_interval(families, config["bootstrap"]["replicates"],
                                                            config["bootstrap"]["seed"])))
    oracle = {metric: sum(h.get(metric, 0) for h in oracle_rows) for metric in SUMS[:10]}
    oracle["qa"] = combine_readings(oracle_rows)
    resources = {name: report[name] for name in ("verifier", "reader", "wall_seconds") if name in report}
    random_seeds = [
        {"mode": mode, "budget": budget, "seed": seed,
         "verification_attempts": sum(row["verification_attempts"] for row in history_rows),
         "current_accuracy": sum(row["current"] for row in history_rows)
         / sum(row["current_total"] for row in history_rows)}
        for (mode, budget, seed), history_rows in sorted(stochastic.items())
    ]
    return {"histories": len(oracle_rows), "dataset_sha256": config["dataset_sha256"],
            "families": report["families"], "rows": rows, "oracle": oracle,
            "contrasts": contrasts, "random_seeds": random_seeds, "resources": resources}


def score_readings(readings):
    if not readings:
        return {}
    return {mode: {key: fmean(r[mode][key] for r in readings)
                   for key in ("correct", "abstained", "error")} | {"total": 1}
            for mode in ("short", "reasoning")}


def combine_readings(rows):
    return {mode: {key: sum(row["qa"].get(mode, {}).get(key, 0) for row in rows)
                   for key in ("correct", "abstained", "error", "total")}
            for mode in ("short", "reasoning")}


def plot(report, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True, sharey=True)
    for (mode, rows), (budget_axis, calls_axis) in zip(
        ((mode, [row for row in report["rows"] if row["mode"] == mode])
         for mode in ("fixed", "closed-loop")), axes, strict=True
    ):
        for method in sorted({row["method"] for row in rows}):
            points = [row for row in rows if row["method"] == method]
            accuracy = [100 * row["current_accuracy"] for row in points]
            line, = budget_axis.plot([row["budget"] for row in points], accuracy, marker="o",
                                     label=method)
            calls_axis.plot([row["verification_attempts"] for row in points], accuracy,
                            color=line.get_color(), marker="o")
        budget_axis.set(title=mode, xlabel="Requested verification budget (%)",
                        ylabel="Exact memory checks passed (%)")
        calls_axis.set(title=mode, xlabel="Actual logical verifier calls")
        for axis in (budget_axis, calls_axis):
            axis.grid(alpha=0.2)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncols=5, frameon=False)
    fig.savefig(destination, dpi=160)
    plt.close(fig)


def plot_intervals(report, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True, sharey=True)
    for mode, axis in zip(("fixed", "closed-loop"), axes, strict=True):
        for left, right in (("T2", "H-paced"), ("T1", "T1-no-NLI")):
            rows = [r for r in report["contrasts"] if r["mode"] == mode
                    and (r["left"], r["right"]) == (left, right)]
            steps = [r["budget"] for r in rows]
            line, = axis.plot(steps, [100 * r["difference"] for r in rows], marker="o",
                              label=f"{left} minus {right}")
            axis.fill_between(steps, [100 * r["lower"] for r in rows],
                              [100 * r["upper"] for r in rows],
                              color=line.get_color(), alpha=0.18)
        axis.axhline(0, color="black", linewidth=0.7)
        axis.set(title=mode, xlabel="Requested verification budget (%)")
        axis.grid(alpha=0.2)
    axes[0].set_ylabel("Paired accuracy difference (percentage points)")
    axes[0].legend(frameon=False)
    fig.savefig(destination, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    config = json.loads(Path("docs/step30_freeze.json").read_bytes())
    aggregate = summarize(json.loads(args.report.read_bytes()), config)
    args.destination.mkdir(parents=True, exist_ok=True)
    (args.destination / "aggregate.json").write_text(json.dumps(aggregate, indent=2) + "\n", encoding="utf-8")
    plot(aggregate, args.destination / "budget-and-cost.png")
    plot_intervals(aggregate, args.destination / "paired-intervals.png")
