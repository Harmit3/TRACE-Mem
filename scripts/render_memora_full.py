"""Publish aggregate metrics and plots for the frozen full Memora diagnostic."""

from argparse import ArgumentParser
from collections import defaultdict
import json
from pathlib import Path
from statistics import fmean


def quality(rows):
    scored = [row["metrics"] for row in rows if row["metrics"] is not None]
    counts = {"predictions": len(rows), "scored": len(scored),
              "macro_fama": fmean(r["fama_arithmetic"] for r in scored) if scored else None,
              "abstentions": sum(row["answer_abstained"] for row in rows),
              "reader_errors": sum(row["reader_error"] for row in rows),
              "judge_errors": sum(row["missing_reason"] == "judge_error" for row in rows)}
    for group in ("memory_presence", "forgetting_absence"):
        counts[group] = {"correct": sum(row["correct"][group] for row in scored),
                         "total": sum(row["totals"][group] for row in scored)}
    return counts


def aggregate(rows):
    grouped = defaultdict(lambda: defaultdict(list))
    for row in rows:
        key = row["mode"], row["method"], row["requested_percent"], row["planning_horizon"]
        grouped[key][row["seed"]].append(row)
    results = []
    for (mode, method, budget, horizon), seed_rows in sorted(grouped.items()):
        comparisons = []
        for seed, group in sorted(seed_rows.items()):
            by_cutoff = {r["cutoff"]: r for r in group}
            by_task = {t: quality([r for r in group if r["task"] == t])
                       for t in sorted({r["task"] for r in group})}
            comparisons.append({"seed": seed, **quality(group), "tasks": by_task,
                                "historical_wording": quality([r for r in group if r["historical_wording"]]),
                                "per_cutoff": {cutoff: {k: row[k] for k in (
                                    "candidate_reference", "eligible_candidates", "budget_cap",
                                    "verification_attempts", "verification_failures", "stale_targets",
                                    "transitions", "current_facts", "historically_visible_unique_facts",
                                    "modeled_payload_bytes")}
                                    | {"achieved_reference_coverage": row["verification_attempts"] / row["candidate_reference"]
                                       if row["candidate_reference"] else None}
                                    for cutoff, row in by_cutoff.items()}})
        means = [c["macro_fama"] for c in comparisons if c["macro_fama"] is not None]
        results.append({"mode": mode, "method": method, "requested_percent": budget,
                        "planning_horizon": horizon, "macro_fama_seed_mean": fmean(means) if means else None,
                        "actual_calls_seed_mean": fmean(sum(x["verification_attempts"] for x in r["per_cutoff"].values())
                                                       for r in comparisons),
                        "seeds": comparisons})
    return results


def plot(summary, folder, primary_horizon):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "memora-step24"
    import matplotlib.pyplot as plt

    def save(fig, name):
        path = folder / name
        fig.tight_layout()
        fig.savefig(path, metadata={"Date": None})
        path.write_bytes(b"\n".join(row.rstrip() for row in path.read_bytes().splitlines()) + b"\n")
        plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8), sharey=True)
    for ax, mode in zip(axes, ("fixed", "closed-loop")):
        selected = [r for r in summary["curves"] if r["mode"] == mode
                    and r["planning_horizon"] == primary_horizon and r["macro_fama_seed_mean"] is not None]
        for method in sorted({r["method"] for r in selected}):
            rows = [r for r in selected if r["method"] == method]
            ax.plot([r["actual_calls_seed_mean"] for r in rows], [r["macro_fama_seed_mean"] for r in rows],
                    ".-", alpha=.75, label=method)
        ax.set(title=mode, xlabel="Logical verifier calls, pooled over unique cutoffs", ylim=(-.025, 1.025))
        ax.grid(alpha=.2)
    axes[0].set_ylabel("Adapted local macro FAMA")
    if axes[1].lines:
        axes[1].legend(ncols=2, fontsize=7)
    save(fig, "budget.svg")

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.5))
    e = summary["extraction"]
    a = summary["replay"]["audit"]["counts"]
    axes[0].bar(["User turns", "Claim turns", "Claims"],
                [e["user_turns"], e["claim_turns"], e["claims"]])
    axes[0].set_title("Original extraction coverage")
    axes[1].bar(["Any clash", "Same effective day", "Eligible", "Deferred event-like"],
                [a.get(k, 0) for k in ("any_conflict", "same_effective_day",
                                       "eligible", "deferred_eventlike_clash")])
    axes[1].tick_params(axis="x", labelrotation=30)
    axes[1].set_title("B2 reference conflict audit")
    save(fig, "failure-analysis.svg")


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    files = {phase: json.loads((args.run / f"{phase}-report.json").read_bytes())
             for phase in ("extraction", "replay", "judge")}
    rows = json.loads((args.run / "judged-rows.json").read_bytes())
    curves = aggregate(rows)
    args.report.mkdir(parents=True, exist_ok=True)
    stats = {**files, "curves": curves}
    (args.report / "aggregate.json").write_text(json.dumps(stats, indent=2, sort_keys=True) + "\n",
                                                encoding="utf-8", newline="\n")
    from scripts.extract_memora_full import DESIGN
    plot(stats, args.report, json.loads(DESIGN.read_bytes())["primary_horizon"])
