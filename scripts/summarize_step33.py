"""Publish aggregates and plots without benchmark source text or predictions."""

from argparse import ArgumentParser
import json
from pathlib import Path

from scripts.run_memora import write


def render(root, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = {name: json.loads((root / file).read_bytes()) for name, file in (
        ("validation", "report.json"), ("step32_audit", "step32-audit.json"),
        ("judge_audit", "secondary-judge.json"))}
    destination.mkdir(parents=True, exist_ok=True)
    write(destination / "metrics.json", data)
    result = data["validation"]
    fig, (quality, outcomes) = plt.subplots(1, 2, figsize=(10.5, 4), constrained_layout=True)
    for offset, (arm, scores) in enumerate(result["arms"].items()):
        bars = [scores["extraction"][k] for k in ("precision", "recall", "f1")]
        bars.append(scores["reader"]["accuracy"])
        quality.bar([x + (offset - .5) * .35 for x in range(len(bars))], bars, width=.34, label=arm)
    quality.set(xticks=range(4), xticklabels=("Precision", "Recall", "F1", "Reader accuracy"),
                ylim=(0, 1.05), title="Fictional validation")
    quality.legend()
    ids = tuple(dict.fromkeys(r["id"].rsplit("-", 1)[0] for r in result["rows"]))
    for i, family in enumerate(ids):
        rows = [r for r in result["rows"] if r["id"].rsplit("-", 1)[0] == family]
        for offset, arm in enumerate(("original", "candidate")):
            n = sum((r[arm]["failed"] or r[arm]["correct"] < r[arm]["expected"]
                     or r[arm]["correct"] < r[arm]["predicted"]) if r["type"] == "extraction"
                    else r[arm] != "correct" for r in rows)
            outcomes.barh(i + (offset - .5) * .35, n, height=.34, color=("C0", "C1")[offset])
    outcomes.set(yticks=range(len(ids)), yticklabels=ids, xlabel="Cases with errors",
                 title="Failure counts by fixture family")
    outcomes.invert_yaxis()
    fig.savefig(destination / "validation.png", dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    render(args.output, args.destination)
