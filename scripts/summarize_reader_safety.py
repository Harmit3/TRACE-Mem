"""Adjudicate and publish Step 26 without exposing rubric data to retrieval or generation."""

from argparse import ArgumentParser
from collections import defaultdict
import csv
import json
from pathlib import Path
from statistics import fmean
import time

from scripts.compare_local_verifiers import QWEN, SETTINGS, local_json
from scripts.extract_memora_full import input_history, seed_cache
from scripts.judge_memora_full import read_rubric
from scripts.run_memora import ROOT, sha, write
from scripts.run_reader_safety import DESIGN, MODES
from scripts.score_memora_checks import aggregate_checks, pinned_formula
from scripts.updateset_v2_pilot import QWEN_DIGEST
from trace_mem.local_rubric import judge
from trace_mem.providers import ChatProvider, LimitExceeded, ProviderConfig, ProviderError


VERSIONS = ("original", "v2")


def judge_benchmark(repository, run, previous):
    if (ROOT / "results").resolve() not in run.resolve().parents:
        raise ValueError("Use a local ignored run directory")
    spec, history, revision = input_history(repository)
    rubric = read_rubric(history / f"evaluation_questions_{history.name}.json", spec["question_indices"])
    prediction_path = run / "predictions.json"
    predictions = json.loads(prediction_path.read_bytes())
    expected = {(q, m, r) for q in rubric for m in MODES for r in VERSIONS}
    if len(predictions) != len(expected) or {
            (p["question_id"], p["mode"], p["reader"]) for p in predictions} != expected:
        raise ValueError("Diagnostic predictions are incomplete or outside the protocol")
    if {m["name"]: m["digest"] for m in local_json("/api/tags")["models"]}.get(QWEN) != QWEN_DIGEST:
        raise ValueError("Pinned local judge is unavailable")
    backend = ChatProvider(ProviderConfig("ollama", QWEN, 400, **SETTINGS),
                            run / "benchmark-judge.sqlite")
    seed_cache(backend.database, previous / "benchmark-judge.sqlite")
    formula = pinned_formula(repository, revision)
    memo = {}
    rows = []
    started = time.perf_counter()
    for prediction in predictions:
        q, text = prediction["question_id"], prediction["answer"]
        key = q, text
        if prediction["error"]:
            metrics, missing = None, "reader_error"
        elif key in memo:
            metrics, missing = memo[key]
        else:
            try:
                data = rubric[q]
                checks = {item["evaluation_question_id"]: judge(backend, text, item["evaluation_question"])
                          for item in data["evaluation"]["evaluation_questions"]}
                metrics, missing = aggregate_checks(data, checks, formula), None
            except LimitExceeded:
                raise
            except ProviderError:
                metrics, missing = None, "judge_error"
            memo[key] = metrics, missing
        rows.append({k: v for k, v in prediction.items() if k not in {"answer", "citations", "question_id"}}
                     | {"abstained": text is None and not prediction["error"],
                        "metrics": metrics, "missing_reason": missing})
    result = {"configuration": "adapted local Qwen with pinned official FAMA formula",
              "predictions_sha256": sha(prediction_path), "design_sha256": sha(DESIGN),
              "provider": backend.stats(), "judge_wall_seconds": time.perf_counter() - started, "rows": rows}
    write(run / "scored.json", result)
    return result


def groups(rows):
    cohorts = defaultdict(list)
    for row in rows:
        cohorts[row["mode"], row["reader"]].append(row)
    common = set.intersection(*({r["number"] for r in cohort if r["metrics"] is not None}
                                for cohort in cohorts.values()))
    reports = {}
    for (mode, version), subset in cohorts.items():
        scored = [row["metrics"] for row in subset if row["metrics"] is not None]
        values = [row["fama_arithmetic"] for row in scored]
        shared = [row["metrics"]["fama_arithmetic"] for row in subset if row["number"] in common]
        paired = {r["number"] for r in cohorts[mode, "original"] if r["metrics"] is not None} & {
            r["number"] for r in cohorts[mode, "v2"] if r["metrics"] is not None}
        paired_values = [row["metrics"]["fama_arithmetic"] for row in subset if row["number"] in paired]
        report = {"questions": len(subset), "scored": len(scored),
                  "macro_fama_scored": fmean(values) if values else None,
                  "failure_inclusive_macro_fama": sum(values) / len(subset),
                  "common_macro_fama": fmean(shared) if shared else None,
                  "paired_reader_macro_fama": fmean(paired_values) if paired_values else None,
                  "paired_reader_questions": sorted(paired),
                  "errors": sum(row["missing_reason"] == "reader_error" for row in subset),
                  "judge_errors": sum(row["missing_reason"] == "judge_error" for row in subset),
                  "abstained": sum(row["abstained"] for row in subset),
                  "nominated": sum(row["nominated_source_turns"] for row in subset),
                  "retrieved": sum(row["retrieved_turns"] for row in subset),
                  "arithmetic_answers": sum(row["arithmetic"] for row in subset),
                  "canonicalized_abstentions": sum(row["canonicalized"] for row in subset)}
        for key in ("memory_presence", "forgetting_absence"):
            report[key] = {"correct": sum(row["correct"][key] for row in scored),
                           "total": sum(row["totals"][key] for row in scored)}
        reports[f"{mode}/{version}"] = report
    return sorted(common), reports


def reader_gate(diagnostic, criteria):
    validation = {}
    for version in VERSIONS:
        rows = [r for r in diagnostic["validation"] if r["reader"] == version]
        negatives = [r for r in rows if not r["answerable"]]
        positives = [r for r in rows if r["answerable"]]
        validation[version] = {"passed": sum(r["passed"] for r in rows), "cases": len(rows),
                               "answerable_correct": sum(r["passed"] for r in positives),
                               "answerable_cases": len(positives),
                               "unanswerable_correct": sum(r["passed"] for r in negatives),
                               "unanswerable_cases": len(negatives),
                               "citation_contract_valid": sum(r["citation_contract_valid"] for r in rows),
                               "invalid": sum(r["invalid"] for r in rows),
                               "unexpected_answers": sum(r["unexpected_answer"] for r in rows)}
    current = validation["v2"]
    passed = (current["passed"] / current["cases"] >= criteria["minimum_reader_pass_rate"]
              and current["unanswerable_correct"] / current["unanswerable_cases"]
              >= criteria["minimum_unanswerable_accuracy"])
    safety_passes = all(diagnostic["safety"].values())
    return {"validation": validation, "reader_passes": passed,
            "safety_fixture_passes": safety_passes,
            "evidence_deployment_supported": safety_passes and not diagnostic["index_quarantined"]}


def render(run, folder):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "trace-mem-step26"
    import matplotlib.pyplot as plt

    diagnostic = json.loads((run / "diagnostic.json").read_bytes())
    scored = json.loads((run / "scored.json").read_bytes())
    criteria = json.loads(DESIGN.read_bytes())["gate"]
    common, reports = groups(scored["rows"])
    summary = {"common_scored_questions": common, "benchmark": reports, "diagnostic": diagnostic,
               "promotion": reader_gate(diagnostic, criteria), "judge_provider": scored["provider"],
               "judge_wall_seconds": scored["judge_wall_seconds"]}
    folder.mkdir(parents=True, exist_ok=True)
    write(folder / "aggregate.json", summary)
    with (folder / "question-failure-matrix.csv").open("w", encoding="utf-8", newline="") as file:
        fields = ("number", "task", "mode", "reader", "profile", "source_nominations", "retrieved",
                  "context_facts", "status", "arith", "fama")
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in scored["rows"]:
            writer.writerow({"number": row["number"], "task": row["task"], "mode": row["mode"],
                             "reader": row["reader"], "profile": row["profile"],
                             "source_nominations": row["nominated_source_turns"],
                             "retrieved": row["retrieved_turns"], "context_facts": row["context_facts"],
                             "status": row["missing_reason"] or ("abstention" if row["abstained"] else "answer"),
                             "arith": row["arithmetic"],
                             "fama": row["metrics"]["fama_arithmetic"] if row["metrics"] else None})
    figure, axes = plt.subplots(1, 2, figsize=(10.5, 4.4))
    xs = list(range(len(MODES)))
    labels = ("Structured", "Transcript", "Restricted index", "Source oracle")
    for i, version in enumerate(VERSIONS):
        selected = [reports[f"{mode}/{version}"] for mode in MODES]
        offset = [-.18, .18][i]
        for ax, metric in zip(axes, ("failure_inclusive_macro_fama", "scored")):
            ax.bar([x + offset for x in xs], [row[metric] for row in selected], width=.34, label=version)
    axes[0].set(ylabel="Failure-inclusive adapted local FAMA", ylim=(0, 1))
    axes[1].set(ylabel="Scored questions", ylim=(0, 15))
    for ax in axes:
        ax.set_xticks(xs, labels, rotation=20)
        ax.legend()
    figure.tight_layout()
    path = folder / "comparison.svg"
    figure.savefig(path, metadata={"Date": None})
    path.write_bytes(b"\n".join(line.rstrip() for line in path.read_bytes().splitlines()) + b"\n")
    plt.close(figure)
    figure, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    for i, version in enumerate(VERSIONS):
        selected = [reports[f"{mode}/{version}"] for mode in MODES]
        offset = [-.18, .18][i]
        for ax, component in zip(axes, ("memory_presence", "forgetting_absence")):
            ratios = [r[component]["correct"] / r[component]["total"]
                      if r[component]["total"] else 0 for r in selected]
            ax.bar([x + offset for x in xs], ratios, width=.34, label=version)
    for ax, title in zip(axes, ("Memory-presence checks", "Forgetting-absence checks")):
        ax.set(title=title, ylabel="Fraction credited among scored checks", ylim=(0, 1.05))
        ax.set_xticks(xs, labels, rotation=20)
        ax.legend()
    figure.tight_layout()
    path = folder / "rubric-components.svg"
    figure.savefig(path, metadata={"Date": None})
    path.write_bytes(b"\n".join(line.rstrip() for line in path.read_bytes().splitlines()) + b"\n")
    plt.close(figure)
    return summary


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    for name in ("memora", "output", "previous", "publish"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    judge_benchmark(args.memora, args.output, args.previous)
    print(json.dumps(render(args.output, args.publish), sort_keys=True))
