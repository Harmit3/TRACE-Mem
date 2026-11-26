"""Read-only cross-checks and publication figures. No inference or original renderers."""
from collections import Counter, defaultdict
from hashlib import sha256
import csv
import json
from pathlib import Path
import random

import numpy as np


def load(path):
    return json.loads(Path(path).read_bytes())


def midpoint(data, probabilities):
    ordered = sorted(data)
    result = []
    for p in probabilities:
        lower, fraction = divmod(p * (len(ordered) - 1), 1)
        i = int(lower)
        result.append(ordered[i] + fraction * (ordered[min(i + 1, len(ordered)-1)] - ordered[i]))
    return result


def audit(step):
    folder = Path(f"results/step{step}")
    original = load(folder / "report.json")
    histories = [load(p) for p in sorted((folder / "histories").glob("*.json"))]
    assert histories == original["histories"]
    assert len({h["history"] for h in histories}) == len(histories) == 100
    families = Counter(h["family"] for h in histories)
    assert len(families) == 10 and set(families.values()) == {10}
    published = load(f"docs/step{step}_artifacts/aggregate.json")
    freeze = load(f"docs/step{step}_freeze.json")
    rows = defaultdict(dict)
    total_calls = deletion = 0
    for h in histories:
        grouped = defaultdict(list)
        for r in h["rows"]:
            m, mode, b, horizon = r["method"], r["mode"], r["budget"], r.get("horizon")
            assert 0 <= r["verification_attempts"] <= r["budget_cap"]
            if mode == "fixed":
                assert r["verification_attempts"] == r["budget_cap"]
            total_calls += r["verification_attempts"]
            deletion += r["authorized_deletion"]
            grouped[mode, b, horizon, m].append(r)
        for condition, selected in grouped.items():
            if step == 30:
                seeds = freeze["seeds"] if condition[-1] == "B4" else freeze["seeds"][:1]
                assert sorted(r["seed"] for r in selected) == sorted(seeds)
            else:
                assert len(selected) == 1
            rows[condition][h["history"]] = (h["family"], selected)
    table = []
    for p in published["rows"]:
        k = (p["mode"], p["budget"], p.get("horizon"), p["method"])
        selected = rows[k].values()
        for name in ("current", "historical", "current_total", "historical_total", "budget_cap",
                     "verification_attempts", "stale_targets", "authorized_deletion", "logical_input_tokens",
                     "logical_output_tokens"):
            if name in p:
                actual = sum(sum(r[name] for r in rr) / len(rr) for _, rr in selected)
                assert np.isclose(actual, p[name]), (step, k, name)
        numerator = "current_accuracy" if step == 30 else "accuracy"
        assert np.isclose(p[numerator], p["current"] / p["current_total"])
        table.append(dict(step=step, mode=k[0], budget=k[1], horizon=k[2], method=k[3],
                          checks=p["current_total"], correct=p["current"], history_checks=p["historical_total"],
                          history_correct=p["historical"], cap=p["budget_cap"], calls=p["verification_attempts"],
                          stale=p["stale_targets"], accuracy=p[numerator]))
    contrasts = {
        "T2 minus B3": {"T2": 1, "B3": -1},
        "T2 minus H-paced": {"T2": 1, "H-paced": -1},
        "T2 minus T1": {"T2": 1, "T1": -1},
        "T1 minus T1-no-NLI": {"T1": 1, "T1-no-NLI": -1},
        "T2 minus T2-no-NLI": {"T2": 1, "T2-no-NLI": -1},
        "Score by pacing interaction": {"T2": 1, "T2-no-NLI": -1, "T1": -1, "T1-no-NLI": 1},
    }
    for p in published["contrasts"]:
        weights = ({p["left"]: 1, p["right"]: -1} if step == 30 else contrasts[p["contrast"]])
        sample = defaultdict(list)
        for h in histories:
            difference = 0
            for m, sign in weights.items():
                key = (p["mode"], p["budget"],
                       p.get("horizon") if m in {"T2", "T2-no-NLI", "H-paced"} else None, m)
                _, condition = rows[key][h["history"]]
                difference += sign * sum(r["current"] / r["current_total"] for r in condition) / len(condition)
            sample[h["family"]].append(difference)
        means = [sum(values) / len(values) for values in sample.values()]
        rng = random.Random(freeze["bootstrap"]["seed"])
        draws = [sum(means[int(rng.random() * len(means))] for _ in means) / len(means)
                 for _ in range(freeze["bootstrap"]["replicates"])]
        lo, hi = midpoint(draws, (0.025, 0.975))
        assert np.allclose([sum(means) / len(means), lo, hi], [p["difference"], p["lower"], p["upper"]],
                           rtol=0, atol=1e-12)
    if step == 31:
        assert total_calls == original["prior_verifier_uses"] and not original["verifier"]["attempts"]
    else:
        assert total_calls == original["verifier"]["attempts"] + original["verifier"]["cache_hits"]
    return table, {"histories": len(histories), "families": dict(families), "conditions": len(table),
                   "paired_intervals": len(published["contrasts"]), "total_logical_calls": total_calls,
                   "repeated_deletion_checks": deletion, "fresh_verifier_calls": original["verifier"]["attempts"],
                   "report_sha256": sha256((folder / "report.json").read_bytes()).hexdigest()}


def render(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42, "svg.hashsalt": "trace-step34",
                         "axes.spines.top": False, "axes.spines.right": False})
    colors = {"T2": "#0072B2", "H-paced": "#D55E00", "B3": "#009E73"}
    figure, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), layout="constrained", sharey=True)
    for axis, mode in zip(axes, ("fixed", "closed-loop"), strict=True):
        for m, color in colors.items():
            relevant = sorted((r for r in rows if r["step"] == 30 and r["mode"] == mode
                               and r["method"] == m), key=lambda r: r["budget"])
            axis.plot([r["calls"] for r in relevant], [100*r["accuracy"] for r in relevant],
                      "o-", ms=3, color=color, label=m)
        axis.set(title=mode.replace("-", " ").capitalize(), xlabel="Actual verification calls")
        axis.grid(axis="y", alpha=.2)
    axes[0].set_ylabel("Exact memory checks passed (%)")
    axes[0].legend(frameon=False)
    save(figure, "budget-reversal")
    plt.close(figure)

    aggregate = load("docs/step31_artifacts/aggregate.json")
    figure, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), layout="constrained")
    for budget, marker in ((10, "s"), (25, "^"), (50, "o"), (100, "D")):
        contrasts = [r for r in aggregate["contrasts"] if r["contrast"] == "T2 minus B3"
                     and r["budget"] == budget and r["mode"] == "closed-loop"]
        means, low, high = ([100*r[k] for r in contrasts] for k in ("difference", "lower", "upper"))
        axes[0].errorbar([r["horizon"] for r in contrasts], means,
                         yerr=[np.maximum(0, np.subtract(means, low)), np.maximum(0, np.subtract(high, means))],
                         marker=marker, label=f"{budget}%", capsize=2, lw=.9)
        t2 = [r for r in rows if r["step"] == 31 and r["mode"] == "closed-loop"
              and r["method"] == "T2" and r["budget"] == budget]
        axes[1].plot([r["horizon"] for r in t2], [100*r["calls"]/r["cap"] for r in t2],
                     marker=marker, label=f"{budget}%", lw=.9)
    axes[0].axhline(0, color="black", lw=.7)
    axes[0].set_ylabel("T2 minus B3 (percentage points)")
    axes[1].set_ylabel("T2 call allowance used (%)")
    for ax in axes:
        ax.set_xlabel("Planning horizon (% of nominal)")
        ax.set_xticks([40, 60, 100, 140, 200])
        ax.grid(axis="y", alpha=.2)
    axes[1].legend(frameon=False, title="Requested budget")
    save(figure, "horizon-sensitivity")
    plt.close(figure)


def save(figure, name):
    for ext in ("pdf", "svg"):
        metadata = {"CreationDate": None, "ModDate": None} if ext == "pdf" else {"Date": None}
        path = Path(f"research/figures/{name}.{ext}")
        figure.savefig(path, metadata=metadata)
        if ext == "svg":
            path.write_bytes(b"\n".join(line.rstrip() for line in path.read_bytes().splitlines()) + b"\n")


if __name__ == "__main__":
    a, checks_a = audit(30)
    b, checks_b = audit(31)
    with Path("research/tables/verification-grid.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(a[0]))
        writer.writeheader()
        writer.writerows(a + b)
    render(a + b)
    result = {"step30": checks_a, "step31": checks_b}
    Path("research/tables/checkpoint-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
