"""Render the local Step 22 review worksheet and actual budget curves."""

from argparse import ArgumentParser
from collections import defaultdict
import json
from pathlib import Path

from scripts.run_memora import ROOT


def markdown(rows):
    content = [
        "# Memora development review worksheet",
        "",
        "All rows are pending human review. Literal-span proposals have source checks only.",
        "Record the source ID, predicate, value, operation, effective date, and whether the target",
        "is unambiguous. Use pending if the source cannot establish a decision.",
        "",
        "## Focused review",
        "",
    ]
    for row in rows:
        if row["review_note"]:
            content.extend((f"- **{row['source_id']}** {row['review_note']}", "  - Decision/date: ___"))
    session = None
    for row in rows:
        if row["session"] != session:
            session = row["session"]
            content.extend(("", f"## Session {session} ({row['day']})", ""))
        text = " ".join(row["text"].split())
        content.append(f"- **{row['source_id']} {row['speaker']}** {text}")
        if row["proposed_claim"]:
            proposed = row["proposed_claim"]
            content.append(f"  - Source-checked proposal: {proposed['intent']} "
                           f"{proposed['predicate']} = {proposed['value']}")
    return "\n".join(content) + "\n"


def aggregate(report):
    """Reduce fictional rows across histories without serializing transcripts or model answers."""
    totals = defaultdict(lambda: defaultdict(int))
    for result in report["fictional"].values():
        for row in result["rows"]:
            group = (row["condition"], row["mode"], row["method"], row["requested_percent"])
            target = totals[group]
            for key in ("verification_attempts", "verification_failures", "reference_candidates",
                        "budget_cap", "visible_facts", "visible_outside_oracle",
                        "answer_expected_literal", "abstained", "reader_error"):
                target[key] += row[key]
            for label, counts in row["checks"].items():
                for field, value in counts.items():
                    target[f"{label}_{field}"] += value
    return [{"condition": c, "mode": m, "method": a, "requested_percent": p, **value}
            for (c, m, a, p), value in sorted(totals.items())]


def plot(report, path):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "trace-mem-step22"
    import matplotlib.pyplot as plt

    values = defaultdict(lambda: [0, 0, 0])
    for result in report["fictional"].values():
        for row in result["rows"]:
            if row["condition"] != "span-oracle":
                continue
            key = row["mode"], row["method"], row["requested_percent"]
            values[key][0] += row["verification_attempts"]
            values[key][1] += row["checks"]["current"]["correct"]
            values[key][2] += row["checks"]["current"]["total"]
    fig, axes = plt.subplots(1, 2, sharey=True, figsize=(11, 4.8))
    for ax, mode in zip(axes, ("fixed", "closed-loop")):
        for method in ("B0", "B1", "B2", "B3", "B4", "B5", "T1", "T1-no-NLI"):
            points = [values[mode, method, p] for p in (0, 10, 25, 50, 100)]
            ax.plot([r[0] for r in points], [r[1] / r[2] for r in points],
                    ".-", label=method, alpha=0.8)
        ax.set(title=mode, xlabel="Actual verifier calls across two histories", ylim=(0, 1.05))
    axes[0].set_ylabel("Fraction of 16 current-memory checks correct")
    axes[1].legend(fontsize=8, loc="lower right", ncols=2)
    fig.suptitle("Fictional span-oracle diagnostic using frozen controllers")
    fig.tight_layout()
    fig.savefig(path, metadata={"Date": None})
    path.write_bytes(b"\n".join(line.rstrip() for line in path.read_bytes().splitlines()) + b"\n")
    plt.close(fig)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--plot", type=Path)
    parser.add_argument("--aggregate", type=Path)
    args = parser.parse_args()
    if (ROOT / "results").resolve() not in args.run.resolve().parents:
        parser.error("Review worksheets belong under ignored results/")
    run = args.run
    (run / "review-packet.md").write_text(markdown(
        json.loads((run / "review-packet.json").read_bytes())), encoding="utf-8", newline="\n")
    if args.plot or args.aggregate:
        report = json.loads((run / "report.json").read_bytes())
        if args.plot:
            plot(report, args.plot)
        if args.aggregate:
            prefix = report["memora_prefix"]
            summary = {"memora_prefix": {**prefix, "rows": [
                row for row in prefix["rows"] if row["requested_percent"] == 100]},
                "fictional_pooled": aggregate(report),
                "fictional_stream_counts": {name: {key: run[key] for key in (
                    "automatic", "oracle_claims", "events", "user_turns", "extraction_failures")}
                    for name, run in report["fictional"].items()},
                "provider": report["provider"], "wall_seconds": report["wall_seconds"]}
            args.aggregate.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                                      encoding="utf-8", newline="\n")
