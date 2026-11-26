"""Score authorized recovery separately and compare archived diagnostic arms."""

from argparse import ArgumentParser
import csv
import json
from pathlib import Path
from statistics import fmean
import time

from scripts.compare_local_verifiers import QWEN, SETTINGS, local_json
from scripts.extract_memora_full import input_history
from scripts.judge_memora_full import read_rubric
from scripts.run_memora import ROOT, sha, write
from scripts.run_authorized_evidence import DESIGN
from scripts.score_memora_checks import aggregate_checks, pinned_formula
from scripts.updateset_v2_pilot import QWEN_DIGEST
from trace_mem.local_rubric import judge
from trace_mem.providers import ChatProvider, LimitExceeded, ProviderConfig, ProviderError


COMPARATOR = "9824d8e1f5c6d3a27bde8eb99cfc4a91be2f70e38038df25eecd0b080ef4f6e9"
MODES = ("structured-b2", "transcript-diagnostic", "evidence-index-v1",
         "source-oracle-diagnostic", "authorized-evidence-v2")


def score(repo, output):
    if (ROOT / "results").resolve() not in output.resolve().parents or not json.loads(
            (output / "safety.json").read_bytes())["passes"]:
        raise ValueError("Safety gate did not authorize a local score")
    design, history, revision = input_history(repo)
    candidates = json.loads((output / "predictions.json").read_bytes())
    rubric = read_rubric(history / f"evaluation_questions_{history.name}.json", design["question_indices"])
    if len(candidates) != 15 or {row["question_id"] for row in candidates} != set(rubric):
        raise ValueError("Prediction set differs from the frozen development rubric")
    if {x["name"]: x["digest"] for x in local_json("/api/tags")["models"]}.get(QWEN) != QWEN_DIGEST:
        raise ValueError("Pinned judge not available")
    formula = pinned_formula(repo, revision)
    backend = ChatProvider(ProviderConfig("ollama", QWEN, 160, **SETTINGS), output / "judge.sqlite")
    started = time.perf_counter()
    result = []
    for row in candidates:
        metrics = None
        if row["error"]:
            missing = "reader_error"
        else:
            try:
                item = rubric[row["question_id"]]
                checks = {q["evaluation_question_id"]: judge(
                    backend, row["answer"], q["evaluation_question"])
                    for q in item["evaluation"]["evaluation_questions"]}
                metrics = aggregate_checks(item, checks, formula)
                missing = None
            except LimitExceeded:
                raise
            except ProviderError:
                missing = "judge_error"
        result.append({k: v for k, v in row.items() if k not in {"answer", "question_id", "error"}}
                      | {"abstained": row["answer"] is None and not row["error"],
                         "metrics": metrics, "missing_reason": missing})
    report = {"rows": result, "provider": backend.stats(), "wall_seconds": time.perf_counter() - started,
              "scorer": "adapted local Qwen checks with pinned official FAMA arithmetic",
              "predictions_sha256": sha(output / "predictions.json")}
    write(output / "scored.json", report)
    return report


def metrics(rows, common):
    scored = [r for r in rows if r["metrics"] is not None]
    value = lambda row: row["metrics"]["fama_arithmetic"]
    result = {"scored": len(scored), "questions": len(rows),
              "failure_inclusive_macro_fama": sum(map(value, scored)) / len(rows),
              "scored_macro_fama": fmean(map(value, scored)) if scored else None,
              "common_macro_fama": fmean(value(r) for r in scored if r["number"] in common) if common else None,
              "abstained": sum(r["abstained"] for r in rows),
              "invalid_outputs": sum(r["missing_reason"] == "reader_error" for r in rows),
              "judge_errors": sum(r["missing_reason"] == "judge_error" for r in rows),
              "retrieved": sum(r["retrieved_turns"] for r in rows),
              "nominated": sum(r["nominated_source_turns"] for r in rows)}
    for area in ("memory_presence", "forgetting_absence"):
        result[area] = {name: sum(r["metrics"][group][area] for r in scored)
                        for name, group in (("correct", "correct"), ("total", "totals"))}
    return result


def plots(summary, publish):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "trace-mem-step29"
    import matplotlib.pyplot as plt
    labels = ["Structured B2", "Transcript", "V1 quarantined", "Source oracle", "V2 authorized"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(11.2, 4.5))
    r = [summary[mode] for mode in MODES]
    a.bar(labels, [x["retrieved"] / x["nominated"] for x in r], color="#397781")
    b.bar(labels, [x["failure_inclusive_macro_fama"] for x in r], color="#985f33")
    a.set(ylabel="Fraction of nominated source turns retrieved", ylim=(0, 1))
    b.set(ylabel="Failure-inclusive adapted local macro FAMA", ylim=(0, 1))
    for ax in (a, b):
        ax.tick_params(axis="x", labelrotation=25)
    fig.tight_layout()
    path = publish / "comparison.svg"
    fig.savefig(path, metadata={"Date": None})
    path.write_bytes(b"\n".join(line.rstrip() for line in path.read_bytes().splitlines()) + b"\n")
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.5))
    for ax, key, title in zip(axes, ("memory_presence", "forgetting_absence"),
                              ("Memory presence", "Forgetting absence")):
        ax.bar(labels, [row[key]["correct"] / row[key]["total"] for row in r], color="#397781")
        ax.set(title=title, ylabel="Fraction of scorable checks credited", ylim=(0, 1.05))
        ax.tick_params(axis="x", labelrotation=25)
    fig.tight_layout()
    path = publish / "rubric-components.svg"
    fig.savefig(path, metadata={"Date": None})
    path.write_bytes(b"\n".join(line.rstrip() for line in path.read_bytes().splitlines()) + b"\n")
    plt.close(fig)


def publish(output, compared, folder):
    if sha(compared) != COMPARATOR:
        raise ValueError("Unexpected archived Step 26 scorer file")
    archived = json.loads(compared.read_bytes())["rows"]
    report = json.loads((output / "scored.json").read_bytes())
    diagnostic = json.loads((output / "diagnostic.json").read_bytes())
    rows = [r for r in archived if r["reader"] == "v2"] + report["rows"]
    groups = {mode: [r for r in rows if r["mode"] == mode] for mode in MODES}
    if any({r["number"] for r in g} != set(range(1, 16)) or len(g) != 15 for g in groups.values()):
        raise ValueError("Comparison coverage does not match")
    common = set.intersection(*({r["number"] for r in group if r["metrics"] is not None}
                                for group in groups.values()))
    summary = {mode: metrics(group, common) for mode, group in groups.items()}
    folder.mkdir(parents=True, exist_ok=True)
    write(folder / "aggregate.json", {"protocol_sha256": sha(DESIGN), "diagnostic": diagnostic,
          "judge_stats": report["provider"], "judge_wall_seconds": report["wall_seconds"],
          "common_scored_questions": sorted(common), "benchmarks": summary})
    with (folder / "question-matrix.csv").open("w", encoding="utf-8", newline="") as file:
        out = csv.writer(file, lineterminator="\n")
        out.writerow(("number", "task", "mode", "retrieved", "nominated", "status", "fama"))
        for row in sorted(rows, key=lambda x: (x["number"], x["mode"])):
            out.writerow((row["number"], row["task"], row["mode"], row["retrieved_turns"],
                          row["nominated_source_turns"], row["missing_reason"] or (
                          "abstained" if row["abstained"] else "answer"),
                          row["metrics"]["fama_arithmetic"] if row["metrics"] else None))
    plots(summary, folder)
    return summary


if __name__ == "__main__":
    p = ArgumentParser(description=__doc__)
    for name in ("memora", "output", "archived_step26_scores", "publish"):
        p.add_argument(name, type=Path)
    args = p.parse_args()
    score(args.memora, args.output)
    print(json.dumps(publish(args.output, args.archived_step26_scores, args.publish), sort_keys=True))
