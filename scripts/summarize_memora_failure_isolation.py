"""Score and summarize the failure-isolation run in a rubric-only process."""

from argparse import ArgumentParser
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
from statistics import fmean
import time

from scripts.compare_local_verifiers import QWEN, SETTINGS, local_json
from scripts.extract_memora_full import input_history
from scripts.judge_memora_full import read_rubric
from scripts.run_memora import ROOT, sha, write
from scripts.run_memora_failure_isolation import DESIGN
from scripts.score_memora_checks import aggregate_checks, pinned_formula
from scripts.updateset_v2_pilot import QWEN_DIGEST
from trace_mem.local_rubric import judge
from trace_mem.providers import ChatProvider, LimitExceeded, ProviderConfig, ProviderError


MODES = ("structured-b2", "transcript-diagnostic", "source-oracle-diagnostic")


def adjudicate(source, output):
    if (ROOT / "results").resolve() not in output.resolve().parents:
        raise ValueError("Use ignored local results")
    design = json.loads(DESIGN.read_bytes())
    file = output / "predictions.json"
    rows = json.loads(file.read_bytes())
    protocol, history, pin = input_history(source)
    rubric = read_rubric(history / f"evaluation_questions_{history.name}.json", protocol["question_indices"])
    if ({row["question_id"] for row in rows} != set(rubric)
            or {(row["question_id"], row["mode"]) for row in rows}
            != {(q, mode) for q in rubric for mode in MODES} or len(rows) != 3 * len(rubric)):
        raise ValueError("Incomplete or out-of-scope diagnostic predictions")
    if {m["name"]: m["digest"] for m in local_json("/api/tags")["models"]}.get(QWEN) != QWEN_DIGEST:
        raise ValueError("Pinned local judge is not available")
    formula = pinned_formula(source, pin)
    backend = ChatProvider(ProviderConfig("ollama", QWEN, design["max_judge_requests"], **SETTINGS),
                           output / "benchmark-judge.sqlite")
    checked, memo = [], {}
    started = time.perf_counter()
    for row in rows:
        key = row["question_id"], row["answer"]
        metrics = None
        missing = None
        if row["error"]:
            missing = "reader_error"
        elif key in memo:
            metrics, missing = memo[key]
        else:
            checks = {}
            rubric_row = rubric[row["question_id"]]
            try:
                for item in rubric_row["evaluation"]["evaluation_questions"]:
                    checks[item["evaluation_question_id"]] = judge(
                        backend, row["answer"], item["evaluation_question"])
                metrics = aggregate_checks(rubric_row, checks, formula)
            except LimitExceeded:
                raise
            except ProviderError:
                missing = "judge_error"
            memo[key] = metrics, missing
        checked.append({k: v for k, v in row.items() if k not in {"answer", "citations", "question_id"}}
                       | {"abstained": row["answer"] is None and not row["error"],
                          "metrics": metrics, "missing_reason": missing})
    result = {"judge": "adapted local Qwen with exact pinned Memora FAMA arithmetic",
              "replay_predictions_sha256": sha(file), "provider": backend.stats(),
              "score_wall_seconds": time.perf_counter() - started, "rows": checked}
    write(output / "benchmark-scored.json", result)
    return result


def summarize(scored):
    result = {}
    for mode in MODES:
        subset = [row for row in scored["rows"] if row["mode"] == mode]
        available = [row["metrics"] for row in subset if row["metrics"] is not None]
        get = lambda field: sum(row[field] for row in subset)
        report = {"questions": len(subset), "scored": len(available),
                  "abstentions": get("abstained"), "reader_errors": sum(bool(row["error"]) for row in subset),
                  "judge_errors": sum(row["missing_reason"] == "judge_error" for row in subset),
                  "nominated_turns": get("nominated_source_turns"),
                  "retrieved_nominated_turns": get("retrieved_turns"),
                  "extracted_nominated_turns": get("extracted_turns"),
                  "represented_nominated_turns": get("represented_turns"),
                  "total_context_bytes": get("context_payload_bytes"),
                  "macro_fama": fmean(x["fama_arithmetic"] for x in available) if available else None}
        for key in ("memory_presence", "forgetting_absence"):
            report[key] = {"correct": sum(x["correct"][key] for x in available),
                           "total": sum(x["totals"][key] for x in available)}
        result[mode] = report
    return result


def render(output, publish):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "trace-mem-step25"
    import matplotlib.pyplot as plt

    scored = json.loads((output / "benchmark-scored.json").read_bytes())
    diag = json.loads((output / "diagnostics.json").read_bytes())
    terminal = json.loads((output / "terminal-analysis.json").read_bytes())
    sums = summarize(scored)
    contract = output / "contract-probe.json"
    valid_for_all = set.intersection(*({
        r["number"] for r in scored["rows"] if r["mode"] == mode and r["metrics"] is not None
    } for mode in MODES))
    common = summarize({"rows": [r for r in scored["rows"] if r["number"] in valid_for_all]})
    publish.mkdir(parents=True, exist_ok=True)
    write(publish / "aggregate.json", {"retrieval": sums, "common_scored_questions": sorted(valid_for_all),
          "common_scored_comparison": common, "reader_probe": diag,
          "terminal": [{k: v for k, v in row.items() if k not in {"question", "request_key"}}
                       for row in terminal],
          "contract_probe": json.loads(contract.read_bytes()) if contract.exists() else None,
          "benchmark_provider": scored["provider"], "benchmark_wall_seconds": scored["score_wall_seconds"]})
    matrix = defaultdict(dict)
    for row in scored["rows"]:
        matrix[row["number"]][row["mode"]] = row
    items = []
    for n, modes in sorted(matrix.items()):
        a, b, c = (modes[m] for m in MODES)
        item = {"question_number": n, "task": a["task"], "nominated": a["nominated_source_turns"],
                "extracted": a["extracted_turns"], "represented": a["represented_turns"],
                "structured_retrieved": a["retrieved_turns"], "transcript_retrieved": b["retrieved_turns"],
                "oracle_retrieved": c["retrieved_turns"]}
        flags = []
        if item["nominated"] > item["extracted"]:
            flags.append("source-turn extraction gap")
        if item["extracted"] > item["represented"]:
            flags.append("temporal-state representation gap")
        if item["represented"] > item["structured_retrieved"]:
            flags.append("structured retrieval gap")
        for key, row in zip(("structured", "transcript", "oracle"), (a, b, c)):
            item[f"{key}_status"] = ("invalid/error" if row["error"] else
                                      "abstained" if row["abstained"] else "answer")
            item[f"{key}_fama"] = row["metrics"]["fama_arithmetic"] if row["metrics"] else None
            if row["missing_reason"] == "judge_error":
                flags.append(f"{key} judge failure")
        item["observed_stage_gaps"] = "; ".join(flags)
        items.append(item)
    with (publish / "failure-matrix.csv").open("w", encoding="utf-8", newline="") as file:
        matrix_writer = csv.DictWriter(file, fieldnames=list(items[0]), lineterminator="\n")
        matrix_writer.writeheader()
        matrix_writer.writerows(items)

    figure, axes = plt.subplots(1, 2, figsize=(10, 4.1))
    labels = ["Structured B2", "Transcript", "Source oracle"]
    counts = [sums[key] for key in MODES]
    axes[0].bar(labels, [row["retrieved_nominated_turns"] / row["nominated_turns"] for row in counts])
    axes[0].set(ylabel="Fraction of nominated source turns retrieved", ylim=(0, 1))
    replied = [row["questions"] - row["abstentions"] - row["reader_errors"] for row in counts]
    abstained = [row["abstentions"] for row in counts]
    axes[1].bar(labels, replied, label="Nonempty answer")
    axes[1].bar(labels, abstained, bottom=replied, label="Abstained")
    axes[1].bar(labels, [row["reader_errors"] for row in counts],
                bottom=[r + a for r, a in zip(replied, abstained)], label="Invalid/error")
    axes[1].set(ylabel="Development questions", ylim=(0, 15))
    axes[1].legend(fontsize=8)
    figure.tight_layout()
    plot = publish / "comparison.svg"
    figure.savefig(plot, metadata={"Date": None})
    plot.write_bytes(b"\n".join(line.rstrip() for line in plot.read_bytes().splitlines()) + b"\n")
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(10, 4.1))
    structured = sums["structured-b2"]
    axes[0].bar(["Nominated", "Extracted", "In B2 state", "In reader input"],
                [structured[name] for name in ("nominated_turns", "extracted_nominated_turns",
                                               "represented_nominated_turns", "retrieved_nominated_turns")])
    axes[0].set(ylabel="Question–source nominations", title="Structured evidence attrition")
    axes[0].tick_params(axis="x", labelrotation=20)
    axes[1].bar(labels, [row["macro_fama"] if row["macro_fama"] is not None else 0 for row in counts])
    for i, row in enumerate(counts):
        if row["macro_fama"] is None:
            axes[1].text(i, 0, "unscored", ha="center", va="bottom", fontsize=8)
    axes[1].set(ylabel="Adapted local macro FAMA", ylim=(0, 1))
    figure.tight_layout()
    plot = publish / "stage-isolation.svg"
    figure.savefig(plot, metadata={"Date": None})
    plot.write_bytes(b"\n".join(line.rstrip() for line in plot.read_bytes().splitlines()) + b"\n")
    plt.close(figure)

    packet = json.loads((output / "human-review.json").read_bytes())
    lines = ["# Step 25 human review", "", "All items await human review. Source candidates are suggestions.", ""]
    for case in packet:
        lines += [f"## {case['number']}. {case['question']}", "", case["review"],
                  "Decision / evidence coverage / privacy notes: ___", ""]
        for item in case["source_candidates"]:
            lines += [f"- {item['source']} · {' '.join(item['text'].split())}"]
        for comp in case["comparisons"]:
            sources = ", ".join(comp["retained_sources"])
            lines += [f"- {comp['mode']} · sources {sources} · outcome {comp['reader_error'] or comp['answer'] or 'abstained'}"]
        lines.append("")
    (output / "human-review.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return sums


if __name__ == "__main__":
    p = ArgumentParser(description=__doc__)
    for name in ("source", "output", "publish"):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    adjudicate(a.source, a.output)
    print(json.dumps(render(a.output, a.publish), sort_keys=True))
