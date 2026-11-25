"""Summarize fixed and causal budget-performance curves over paired development histories."""

from argparse import ArgumentParser
from collections import defaultdict
import json
from pathlib import Path
from statistics import fmean


def aggregate(rows):
    grouped = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["mode"], row["method"], row["requested"]][row["seed"]].append(row)
    summaries = []
    for (mode, method, budget), seeds in sorted(grouped.items()):
        by_seed = []
        for seed, group in sorted(seeds.items()):
            metrics = {"seed": seed}
            for key in ("verification_attempts", "verification_failures", "budget_cap",
                        "reference_candidates", "harmful_current_adoptions"):
                metrics[key] = sum(row[key] for row in group)
            for category in ("current", "historical", "deletion"):
                metrics[category] = sum(row["checks"][category]["correct"] for row in group)
                metrics[f"{category}_total"] = sum(row["checks"][category]["total"] for row in group)
            by_seed.append(metrics)
        mean = {key: fmean(row[key] for row in by_seed) for key in by_seed[0] if key != "seed"}
        summaries.append({"mode": mode, "method": method, "requested_percent": budget,
                          "mean": mean, "by_seed": by_seed})
    return summaries


def plot(summary, path):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "trace-mem-step23"
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7), sharey=True)
    methods = sorted({row["method"] for row in summary})
    for ax, mode in zip(axes, ("fixed", "closed-loop")):
        for method in methods:
            rows = [row for row in summary if row["mode"] == mode and row["method"] == method]
            x = [row["mean"]["verification_attempts"] for row in rows]
            y = [row["mean"]["current"] / row["mean"]["current_total"] for row in rows]
            ax.plot(x, y, ".-", label=method)
            if method == "B4":
                lows = [min(p["current"] / p["current_total"] for p in row["by_seed"]) for row in rows]
                highs = [max(p["current"] / p["current_total"] for p in row["by_seed"]) for row in rows]
                ax.vlines(x, lows, highs, alpha=.45, linewidth=2)
        ax.set_title(mode)
        ax.set_xlabel("Actual calls across two histories (mean for B4)")
        ax.grid(alpha=.2)
    axes[0].set_ylabel("Fraction of current-state checks correct")
    axes[1].legend(ncols=2, fontsize=8)
    fig.suptitle("Frozen T1 versus adaptive allocation on fresh development fixtures")
    fig.tight_layout()
    fig.savefig(path, metadata={"Date": None})
    path.write_bytes(b"\n".join(line.rstrip() for line in path.read_bytes().splitlines()) + b"\n")
    plt.close(fig)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--plot", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_bytes())
    summary = aggregate(report.pop("rows"))
    args.aggregate.write_text(json.dumps({**report, "budget_curves": summary}, indent=2,
                                         sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    plot(summary, args.plot)
