"""Regenerate the Step 34 vector figures from verified released metrics."""
import numpy as np


def render(derived, checks, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = [r | {"calls": r["verification_attempts"], "cap": r["budget_cap"],
                 "accuracy": r.get("current_accuracy", r.get("accuracy"))} for r in derived]
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
    save(figure, "budget-reversal", output)
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), layout="constrained")
    for budget, marker in ((10, "s"), (25, "^"), (50, "o"), (100, "D")):
        contrasts = [r for r in checks if r.get("contrast") == "T2 minus B3"
                     and r["budget"] == budget and r["mode"] == "closed-loop"]
        means, low, high = ([100*r[k] for r in contrasts] for k in ("difference", "lower", "upper"))
        axes[0].errorbar([r["horizon"] for r in contrasts], means,
                         yerr=[np.maximum(0, np.subtract(means, low)), np.maximum(0, np.subtract(high, means))],
                         marker=marker, label=f"{budget}%", capsize=2, lw=.9)
        t2 = [r for r in rows if r["step"] == 31 and r["mode"] == "closed-loop"
              and r["method"] == "T2" and r["budget"] == budget]
        t2.sort(key=lambda r: r["horizon"])
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
    save(figure, "horizon-sensitivity", output)
    plt.close(figure)


def save(figure, name, output):
    for ext in ("pdf", "svg"):
        metadata = {"CreationDate": None, "ModDate": None} if ext == "pdf" else {"Date": None}
        path = output / f"{name}.{ext}"
        figure.savefig(path, metadata=metadata)
        if ext == "svg":
            path.write_bytes(b"\n".join(line.rstrip() for line in path.read_bytes().splitlines()) + b"\n")
