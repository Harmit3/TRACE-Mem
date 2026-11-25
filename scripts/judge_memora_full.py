"""Adjudicate full development predictions with the frozen, adapted local Qwen judge."""

from argparse import ArgumentParser
import hashlib
import json
from pathlib import Path
import time

from scripts.compare_local_verifiers import QWEN, SETTINGS, local_json
from scripts.extract_memora_full import DESIGN, input_history
from scripts.run_memora import ROOT, sha, write
from scripts.score_memora_checks import aggregate_checks, pinned_formula
from scripts.updateset_v2_pilot import QWEN_DIGEST
from scripts.validate_memora_quality import PROTOCOL as JUDGE_VALIDATION
from trace_mem.local_rubric import JUDGE_PROMPT, judge
from trace_mem.providers import ChatProvider, LimitExceeded, ProviderConfig, ProviderError


def read_rubric(path, selectors):
    groups = json.loads(path.read_bytes())["questions"]
    selected = {groups[task][i]["question_id"]: groups[task][i]
                for task, items in selectors.items() for i in items}
    if len(selected) != sum(map(len, selectors.values())):
        raise ValueError("Duplicate rubric question identifier")
    return selected


def run(repository, output, validation):
    if (ROOT / "results").resolve() not in output.resolve().parents:
        raise ValueError("Use an ignored results directory")
    design, history, revision = input_history(repository)
    verified = json.loads(validation.read_bytes())
    if (verified["protocol_sha256"] != sha(JUDGE_VALIDATION)
            or verified["qwen_digest"] != QWEN_DIGEST or not verified["judge"]["passes"]):
        raise ValueError("Use the original passing local judge validation report")
    tags = {m["name"]: m["digest"] for m in local_json("/api/tags")["models"]}
    if tags.get(QWEN) != QWEN_DIGEST:
        raise ValueError("Pinned judge model is missing")
    predictions = output / "predictions.json"
    rows = json.loads(predictions.read_bytes())
    rubric = read_rubric(history / f"evaluation_questions_{history.name}.json", design["question_indices"])
    if {x["question_id"] for x in rows} != set(rubric):
        raise ValueError("Predictions must cover the frozen development questions")
    formula = pinned_formula(repository, revision)
    freeze = {"predictions_sha256": sha(predictions), "validation_sha256": sha(validation),
              "design_sha256": sha(DESIGN), "judge_code_sha256": sha(Path(__file__)),
              "prompt": JUDGE_PROMPT, "qwen": QWEN_DIGEST, "settings": SETTINGS,
              "rubric_scope": "development-only"}
    manifest = output / "judge-freeze.json"
    if manifest.exists() and json.loads(manifest.read_bytes()) != freeze:
        raise ValueError("Scoring freeze changed")
    write(manifest, freeze)
    directory = output / "adjudicated"
    directory.mkdir(exist_ok=True)
    provider = ChatProvider(ProviderConfig("ollama", QWEN, design["max_judge_requests"], **SETTINGS),
                            output / "judge.sqlite")
    started = time.perf_counter()
    checked = []
    reused = 0
    memo = {}
    for ordinal, row in enumerate(rows, 1):
        answer = row["answer"]
        key = json.dumps([row["question_id"], answer, row["reader_error"]], ensure_ascii=False)
        checkpoint = directory / (hashlib.sha256(key.encode()).hexdigest() + ".json")
        if key in memo:
            outcome = memo[key]
            reused += 1
        elif checkpoint.exists():
            outcome = json.loads(checkpoint.read_bytes())
            memo[key] = outcome
        else:
            question = rubric[row["question_id"]]
            checks = {}
            if row["reader_error"]:
                outcome = {"metrics": None, "missing_reason": "reader_error"}
            else:
                try:
                    for check in question["evaluation"]["evaluation_questions"]:
                        checks[check["evaluation_question_id"]] = judge(
                            provider, answer, check["evaluation_question"])
                    metrics = aggregate_checks(question, checks, formula)
                    outcome = {"metrics": metrics, "missing_reason": None}
                except LimitExceeded:
                    raise
                except ProviderError:
                    outcome = {"metrics": None, "missing_reason": "judge_error"}
            write(checkpoint, outcome)
            memo[key] = outcome
        checked.append({k: v for k, v in row.items() if k not in {"answer", "citations"}}
                       | {"answer_abstained": answer is None and not row["reader_error"]} | outcome)
        if ordinal % 500 == 0:
            print(json.dumps({"prediction_rows_adjudicated": ordinal, "distinct_answer_keys": len(memo)}),
                  flush=True)
    write(output / "judged-rows.json", checked)
    result = {"configuration": "adapted local Qwen judge with pinned official FAMA arithmetic",
              "rows": len(checked), "scored": sum(x["metrics"] is not None for x in checked),
              "distinct_answer_keys": len(memo), "duplicate_answer_rows_reused": reused,
              "provider": provider.stats(), "invocation_wall_seconds": time.perf_counter() - started}
    write(output / "judge-report.json", result)
    return result


if __name__ == "__main__":
    p = ArgumentParser(description=__doc__)
    p.add_argument("memora", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--validation", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(run(a.memora, a.output, a.validation), sort_keys=True))
