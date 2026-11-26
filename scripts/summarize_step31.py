"""Render every condition, paired interval and predefined trace stratum."""

from argparse import ArgumentParser
from collections import Counter, defaultdict
from itertools import product
import json
from pathlib import Path

from scripts.run_step31 import PROTOCOL
from scripts.summarize_step30 import paired_interval


COUNTS = ("current", "current_total", "historical", "historical_total", "harmful_adoptions",
          "eligible_candidates", "live_eligible", "verification_attempts", "budget_cap",
          "stale_targets", "verification_failures", "positions_total", "logical_input_tokens",
          "logical_output_tokens", "unmetered_calls", "helpful", "harmful", "deletion",
          "authorized_deletion", "deletion_total")
OUTCOMES = ("correct", "incorrect", "abstained", "invalid", "contradictory")
CONTRASTS = (("T2 minus B3", {"T2": 1, "B3": -1}),
             ("T2 minus H-paced", {"T2": 1, "H-paced": -1}),
             ("T2 minus T1", {"T2": 1, "T1": -1}),
             ("T2 minus T2-no-NLI", {"T2": 1, "T2-no-NLI": -1}),
             ("T1 minus T1-no-NLI", {"T1": 1, "T1-no-NLI": -1}),
             ("Score by pacing interaction", {"T2": 1, "T2-no-NLI": -1,
                                              "T1": -1, "T1-no-NLI": 1}))


def condition(mode, budget, horizon, method):
    return mode, budget, horizon, method


def summarize(report, design):
    totals = defaultdict(Counter)
    scores = defaultdict(dict)
    outcomes = defaultdict(lambda: defaultdict(Counter))
    strata = {}
    expected = {
        condition(mode, budget, horizon, method)
        for budget in design["budgets"]
        for mode, horizon, methods in (
            ("fixed", None, design["baselines"] + design["adaptive"]),
            ("closed-loop", None, design["baselines"]),
            *(("closed-loop", h, design["adaptive"]) for h in design["horizon_percent"]),
        )
        for method in methods
    }
    for history in report["histories"]:
        identity = history["history"]
        found = set()
        for row in history["rows"]:
            key = condition(row["mode"], row["budget"], row["horizon"], row["method"])
            if key in found or identity in scores[key]:
                raise ValueError("Duplicate frozen condition")
            found.add(key)
            totals[key].update({metric: row[metric] for metric in COUNTS})
            if row["authorized_deletion"] != row["deletion_total"] or row["unmetered_calls"]:
                raise ValueError("Safety or token accounting gate failed")
            scores[key][identity] = history["family"], row["current"] / row["current_total"]
            for question, result in row.get("qa", {}).items():
                if result not in OUTCOMES:
                    raise ValueError("Unexpected QA outcome")
                outcomes[key][question][result] += 1
        if expected != found:
            raise ValueError("Incomplete history grid")
        left = scores["closed-loop", 50, 100, "T2"][identity][1]
        right = scores["closed-loop", 50, None, "B3"][identity][1]
        label = "T2 win" if left > right else "T2 loss" if left < right else "tie"
        strata.setdefault(label, {"history": identity, "family": history["family"],
                                  "trace": history["traces"]})
    rows = []
    for key, total in totals.items():
        mode, budget, horizon, method = key
        qa = {question: {label: counts[label] for label in OUTCOMES} | {"total": counts.total()}
              for question, counts in outcomes[key].items()}
        calls = total["verification_attempts"]
        rows.append(dict(total, mode=mode, budget=budget, horizon=horizon, method=method, qa=qa,
                         histories=len(scores[key]),
                         accuracy=total["current"] / total["current_total"],
                         historical_accuracy=total["historical"] / total["historical_total"],
                         utilization=calls / total["budget_cap"] if total["budget_cap"] else None,
                         mean_position=total["positions_total"] / calls if calls else None))
    intervals = []
    for budget in design["budgets"]:
        if budget == 0:
            continue
        for mode, horizon in [("fixed", None), *product(["closed-loop"], design["horizon_percent"])]:
            for name, weights in CONTRASTS:
                arms = {
                    m: scores[mode, budget, h(m, horizon, design), m] for m in weights
                }
                families = defaultdict(list)
                first = next(iter(arms.values()))
                for identity, (family, _) in first.items():
                    families[family].append(sum(w * arms[m][identity][1] for m, w in weights.items()))
                intervals.append(dict(mode=mode, budget=budget, horizon=horizon, contrast=name,
                                      **paired_interval(families, design["bootstrap"]["replicates"],
                                                        design["bootstrap"]["seed"])))
    return {"histories": len(report["histories"]), "rows": rows, "contrasts": intervals,
            "traces": strata, "reproduced": report["reproduced"], "manifest": report["manifest"],
            "verifier": report["verifier"], "reader": report["reader"],
            "wall_seconds": report["wall_seconds"]}


def h(method, horizon, design):
    return horizon if method in design["adaptive"] else None


def plot(aggregate, destination, design):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    for budget, axis in zip(design["budgets"][1:], axes.flat, strict=True):
        for method in [*design["adaptive"], "B3", "B5"]:
            data = [r for r in aggregate["rows"] if r["mode"] == "closed-loop"
                    and r["budget"] == budget and r["method"] == method]
            if method in design["adaptive"]:
                axis.plot([r["horizon"] for r in data], [100 * r["accuracy"] for r in data],
                          marker="o", label=method)
            else:
                axis.axhline(data[0]["accuracy"] * 100, linestyle="--", label=method)
        axis.set(title=f"{budget}% budget", xlabel="Planning horizon (% of nominal opportunities)",
                 ylabel="Exact slot accuracy (%)")
        axis.grid(alpha=0.2)
    axes.flat[0].legend(fontsize=8)
    fig.savefig(destination / "horizon.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True, sharey=True)
    for mode, axis in zip(("fixed", "closed-loop"), axes, strict=True):
        for method in design["baselines"] + design["adaptive"]:
            data = [r for r in aggregate["rows"] if r["mode"] == mode and r["method"] == method
                    and r["horizon"] == h(method, 100 if mode == "closed-loop" else None, design)]
            axis.plot([r["budget"] for r in data], [100 * r["accuracy"] for r in data],
                      marker="o", label=method)
        axis.set(title=mode, xlabel="Requested verification budget (%)", ylabel="Exact slot accuracy (%)")
        axis.grid(alpha=0.2)
    axes[0].legend(fontsize=8)
    fig.savefig(destination / "budget.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True, sharey=True)
    for name, axis in zip(("T2 minus B3", "T2 minus H-paced"), axes, strict=True):
        for horizon in design["horizon_percent"]:
            rows = [r for r in aggregate["contrasts"] if r["contrast"] == name
                    and r["mode"] == "closed-loop" and r["horizon"] == horizon]
            axis.plot([r["budget"] for r in rows], [100 * r["difference"] for r in rows],
                      marker="o", label=f"{horizon}% horizon")
            if horizon == 100:
                axis.fill_between([r["budget"] for r in rows], [100 * r["lower"] for r in rows],
                                  [100 * r["upper"] for r in rows], alpha=0.2)
        axis.axhline(0, color="black", linewidth=0.7)
        axis.set(title=name, xlabel="Requested verification budget (%)",
                 ylabel="Paired difference (percentage points)")
        axis.grid(alpha=0.2)
    axes[0].legend(fontsize=8)
    fig.savefig(destination / "paired.png", dpi=160)
    plt.close(fig)


def write_traces(traces, destination):
    lines = ["# Step 31 decision traces", "",
             "The first frozen history in each predefined closed-loop T2 versus B3 stratum at 50%.",
             "Each sequence is shown under both modes. A stale target consumes a call without applying its verdict.", ""]
    for label, history in traces.items():
        lines.extend((f"## {label} in {history['history']}", ""))
        for arm in history["trace"]:
            lines.extend((f"### {arm['method']} in {arm['mode']}", "",
                          "| Date | Arrival | Proposed | Gold | Live before call | Selected target | Budget before | Verdict | Applied | Memory after |",
                          "|---|---|---|---|---|---|---:|---|---|---|"))
            for turn in arm["turns"]:
                values = [turn[k] or "—" for k in ("day", "kind", "proposal", "expected", "live", "target")]
                values.extend((turn["remaining"], turn["verdict"] or "—",
                               "yes" if turn["applied"] else "no", ", ".join(turn["after"]) or "—"))
                lines.append("| " + " | ".join(map(str, values)) + " |")
            lines.append("")
    destination.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    design = json.loads(PROTOCOL.read_bytes())
    aggregate = summarize(json.loads(args.report.read_bytes()), design)
    args.destination.mkdir(parents=True, exist_ok=True)
    (args.destination / "aggregate.json").write_text(json.dumps(aggregate, indent=2) + "\n", encoding="utf-8")
    write_traces(aggregate["traces"], args.destination / "decision-traces.md")
    plot(aggregate, args.destination, design)
