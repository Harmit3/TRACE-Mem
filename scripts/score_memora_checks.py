"""Run pinned Memora FAMA arithmetic on externally adjudicated development checks."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess

from scripts.run_memora import PROTOCOL, audit_checkout, write


SCORER = "evals/agent_eval/memory_to_answer.py"
SCORER_BLOB = "ca02a714473e19e3f415f2d7db272ac84a46e33a"
TYPES = ("memory_presence", "forgetting_absence")


def pinned_formula(source, revision):
    content = subprocess.check_output(["git", "-C", str(source), "show", f"{revision}:{SCORER}"])
    header = f"blob {len(content)}\0".encode()
    if hashlib.sha1(header + content).hexdigest() != SCORER_BLOB:
        raise ValueError("Official FAMA scorer does not match the pinned source")
    definition, = [node for node in ast.parse(content).body
                   if isinstance(node, ast.FunctionDef) and node.name == "fama_score"]
    module = ast.Module(body=[definition], type_ignores=[])
    namespace = {}
    exec(compile(module, SCORER, "exec"), namespace)
    return namespace["fama_score"]


def aggregate_checks(question, judgments, formula):
    checks = question["evaluation"]["evaluation_questions"]
    keys = {check["evaluation_question_id"] for check in checks}
    if (not checks or set(judgments) != keys or len(checks) != len(keys)
            or any(answer not in ("yes", "no") for answer in judgments.values())):
        raise ValueError("Each rubric check needs exactly one yes/no judgment")
    totals = dict.fromkeys(TYPES, 0)
    correct = dict.fromkeys(TYPES, 0)
    for check in checks:
        group = check["evaluation_type"]
        expected = check["expected_answer"]
        if group not in TYPES or expected not in ("yes", "no"):
            raise ValueError("Unsupported rubric check")
        totals[group] += 1
        correct[group] += judgments[check["evaluation_question_id"]] == expected
    return {"totals": totals, "correct": correct,
            "memory_presence_accuracy": correct[TYPES[0]] / totals[TYPES[0]] if totals[TYPES[0]] else None,
            "forgetting_absence_accuracy": correct[TYPES[1]] / totals[TYPES[1]] if totals[TYPES[1]] else None,
            "fama_arithmetic": formula(correct[TYPES[0]], totals[TYPES[0]],
                                       correct[TYPES[1]], totals[TYPES[1]])}


def score(source, judgments, predictions):
    protocol = json.loads(PROTOCOL.read_bytes())
    revision = audit_checkout(source, protocol)
    formula = pinned_formula(source, revision)
    dev = protocol["development"]
    history = source / dev["path"]
    groups = json.loads((history / f"evaluation_questions_{history.name}.json").read_bytes())["questions"]
    allowed = {groups[task][idx]["question_id"]: groups[task][idx]
               for task, indices in dev["selectors"].items() for idx in indices}
    if judgments["predictions_sha256"] != hashlib.sha256(predictions.read_bytes()).hexdigest():
        raise ValueError("Judgments do not identify the supplied predictions file")
    records = json.loads(predictions.read_bytes())
    key = lambda row: (row["mode"], row["method"], row["question_id"])
    by_key = {key(row): row for row in records}
    supplied = {key(row): row for row in judgments["judgments"]}
    if not by_key or len(by_key) != len(records) or set(by_key) != set(supplied) or len(
            supplied) != len(judgments["judgments"]):
        raise ValueError("Judgment rows must exactly match prediction rows")
    for row in records:
        if row["question_id"] not in allowed or row["reader_error"]:
            raise ValueError("Scoring is limited to complete development predictions")
    return {"configuration": "external judgments with pinned Memora FAMA arithmetic",
            "judge_reference": judgments["judge_reference"], "scorer_blob": SCORER_BLOB,
            "predictions_sha256": judgments["predictions_sha256"],
            "rows": [{"mode": mode, "method": method, "question_id": question, **aggregate_checks(
                allowed[question], supplied[mode, method, question]["checks"], formula)}
                for mode, method, question in sorted(supplied)]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("judgments", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if Path("results").resolve() not in args.output.resolve().parents or args.output.exists():
        parser.error("Use a new score file under ignored results/")
    result = score(args.source, json.loads(args.judgments.read_bytes()), args.predictions)
    write(args.output, result)
