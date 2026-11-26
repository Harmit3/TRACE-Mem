"""Aggregate safe LongMemEval diagnostics and render failure-inclusive comparisons."""

from argparse import ArgumentParser
from collections import Counter, defaultdict
from itertools import product
import json
from pathlib import Path

from scripts.longmemeval_inputs import DESIGN
from scripts.run_memora import write


def summarize(report, design):
    rows = report["rows"]
    names = ["BM25", "MiniLM", "oracle", *[
        f"{method}-{cap}" for method, cap in product(design["methods"], design["caps"])]]
    methods = {}
    for method in names:
        present = [row for row in rows if method in row["methods"]]
        scores = [row["methods"][method] for row in present]
        verdict = Counter(score["judge"] for score in scores)
        run = {"completed": len(scores), "selected": len(rows), "correct": verdict["correct"],
               "judged": verdict["correct"] + verdict["incorrect"],
               "invalid_reader": verdict["invalid-reader"], "invalid_judge": verdict["invalid-judge"],
               "abstained": sum(s["status"] == "abstained" for s in scores),
               "seconds_in_reader": sum(s["latency_seconds"] for s in scores)}
        run["failure_inclusive_accuracy"] = run["correct"] / run["completed"] if run["completed"] else None
        run["scored_only_accuracy"] = run["correct"] / run["judged"] if run["judged"] else None
        for field in ("session_recall", "turn_recall"):
            counts = [s[field] for s in scores if s[field] is not None]
            run[field] = {"hits": sum(x[0] for x in counts), "targets": sum(x[1] for x in counts),
                          "questions": len(counts)}
        for field in ("verification_attempts", "verification_failures", "budget_cap", "eligible_candidates",
                      "logical_input_tokens", "logical_output_tokens", "logical_unmetered_calls",
                      "authorization_rejections", "authorized_fields"):
            run[field] = sum(s.get(field, 0) for s in scores)
        run["verification_utilization"] = (run["verification_attempts"] / run["budget_cap"]
                                            if run["budget_cap"] else None)
        if method.startswith(("T2-", "H-paced-")):
            horizon = design["planning_horizon"]
            run["eligible_minus_planned"] = [s["eligible_candidates"] - horizon for s in scores]
        types = defaultdict(Counter)
        for row in present:
            decision = row["methods"][method]["judge"]
            types[row["type"]]["completed"] += 1
            types[row["type"]]["correct"] += decision == "correct"
            types[row["type"]]["scored"] += decision in {"correct", "incorrect"}
        run["types"] = {kind: dict(counts) for kind, counts in types.items()}
        methods[method] = run
    matched = []
    for cap, learned, baseline in product(design["caps"], ("T1", "T2", "T2-no-NLI"),
                                           ("B1", "B2", "B3", "B5", "H-paced")):
        key, control = f"{learned}-{cap}", f"{baseline}-{cap}"
        paired = [(r["methods"][key], r["methods"][control]) for r in rows
                  if key in r["methods"] and control in r["methods"]
                  and r["methods"][key]["verification_attempts"] == r["methods"][control]["verification_attempts"]]
        matched.append({"cap": cap, "learned": learned, "baseline": baseline, "pairs": len(paired),
                        "equal_nonzero_pairs": sum(a["verification_attempts"] > 0 for a, _ in paired),
                        "learned_correct": sum(a["judge"] == "correct" for a, _ in paired),
                        "baseline_correct": sum(b["judge"] == "correct" for _, b in paired)})
    common = [r for r in rows if r["managed_status"] == "completed"]
    on_common = {method: {"cases": len(common), "correct": sum(
        row["methods"][method]["judge"] == "correct" for row in common)} for method in names}
    return report | {"methods": methods, "matched_spending": matched,
                     "common_with_managed": on_common}


def draw(report, dest):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    items = [(m, r) for m, r in report["methods"].items() if r["completed"]]
    fig, (accuracy, retrieval) = plt.subplots(1, 2, figsize=(13, 5.5), constrained_layout=True)
    for i, (name, row) in enumerate(items):
        accuracy.barh(i, row["failure_inclusive_accuracy"], color="#345a83")
        accuracy.text(0.02, i, f"{row['correct']}/{row['completed']}", color="black",
                      bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"}, va="center", fontsize=8)
        for j, field in enumerate(("session_recall", "turn_recall")):
            data = row[field]
            if data["targets"]:
                retrieval.barh(i + (j - 0.5) * 0.32, data["hits"] / data["targets"], height=0.29,
                               color=("#a55736", "#278072")[j], label=field.replace("_", " ")
                               if not i else None)
    for axis, title in ((accuracy, "Adapted local failure-inclusive accuracy"),
                        (retrieval, "Annotated evidence recall after context trimming")):
        axis.set(xlim=(0, 1), title=title, yticks=range(len(items)), yticklabels=[m for m, _ in items])
        axis.invert_yaxis()
        axis.grid(axis="x", alpha=0.2)
    if retrieval.get_legend_handles_labels()[0]:
        retrieval.legend(loc="lower right")
    fig.savefig(dest, dpi=170)
    plt.close(fig)


def draw_matrix(report, dest):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch

    methods = list(report["methods"])
    rows = report["rows"]
    statuses = ("not run", "incorrect", "invalid-reader", "invalid-judge", "correct")
    colors = ("#d9d9d9", "#af4c40", "#e5ae58", "#845998", "#467f73")
    scores = [[statuses.index(row["methods"].get(method, {}).get("judge", "not run"))
               for row in rows] for method in methods]
    fig, axis = plt.subplots(figsize=(11, 7), constrained_layout=True)
    axis.imshow(scores, cmap=ListedColormap(colors), vmin=-0.5, vmax=len(statuses)-0.5,
                aspect="auto", interpolation="nearest")
    axis.set(xticks=range(len(rows)), xticklabels=[r["case"] for r in rows],
             yticks=range(len(methods)), yticklabels=methods,
             xlabel="Frozen question order", title="Local question-level outcomes")
    axis.legend(handles=[Patch(facecolor=color, label=label) for color, label in zip(colors, statuses)],
                loc="lower center", bbox_to_anchor=(0.5, -0.19), ncols=len(statuses), frameon=False)
    fig.savefig(dest, dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    data = summarize(json.loads(args.report.read_bytes()), json.loads(DESIGN.read_bytes()))
    args.destination.mkdir(parents=True, exist_ok=True)
    write(args.destination / "aggregate.json", data)
    draw(data, args.destination / "comparison.png")
    draw_matrix(data, args.destination / "question-outcomes.png")
