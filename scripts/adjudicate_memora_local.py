"""Apply a validated local Qwen judge to completed Memora development predictions."""

from argparse import ArgumentParser
import hashlib
import json
from pathlib import Path
import time

from scripts.run_memora import PROTOCOL, ROOT, audit_checkout, sha, write
from scripts.score_memora_checks import score
from scripts.updateset_v2_pilot import QWEN_DIGEST
from scripts.validate_memora_quality import PROTOCOL as VALIDATION, provider
from trace_mem.local_rubric import judge


def adjudicate(source, predictions, validation, output):
    if (ROOT / "results").resolve() not in output.resolve().parents:
        raise ValueError("Keep local judge responses under ignored results/")
    gate = json.loads(validation.read_bytes())
    if (gate["protocol_sha256"] != sha(VALIDATION) or gate["qwen_digest"] != QWEN_DIGEST
            or not gate["judge"]["passes"]):
        raise ValueError("The frozen local judge has not passed independent development checks")
    protocol = json.loads(PROTOCOL.read_bytes())
    audit_checkout(source, protocol)
    choice = protocol["development"]
    history = source / choice["path"]
    groups = json.loads((history / f"evaluation_questions_{history.name}.json").read_bytes())["questions"]
    allowed = {groups[task][i]["question_id"]: groups[task][i]["evaluation"]["evaluation_questions"]
               for task, indices in choice["selectors"].items() for i in indices}
    data = predictions.read_bytes()
    rows = json.loads(data)
    if not rows or any(row["question_id"] not in allowed or row["reader_error"] for row in rows):
        raise ValueError("Only complete development predictions can be adjudicated")
    output.mkdir(parents=True, exist_ok=True)
    backend = provider(output / "judge.sqlite")
    started = time.perf_counter()
    judgments = {
        "judge_reference": f"Adapted local Qwen judge {QWEN_DIGEST}; validation {sha(validation)}",
        "predictions_sha256": hashlib.sha256(data).hexdigest(), "judgments": [],
    }
    for row in rows:
        checks = {item["evaluation_question_id"]: judge(
            backend, row["answer"], item["evaluation_question"])
            for item in allowed[row["question_id"]]}
        judgments["judgments"].append({key: row[key] for key in ("mode", "method", "question_id")}
                                      | {"checks": checks})
    results = score(source, judgments, predictions)
    results.update(provider=backend.stats(), wall_seconds=time.perf_counter() - started)
    write(output / "judgments.json", judgments)
    write(output / "local-fama.json", results)
    return results


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("validation", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = adjudicate(args.source, args.predictions, args.validation, args.output)
    print(json.dumps({"rows": len(result["rows"]), "provider": result["provider"],
                      "wall_seconds": result["wall_seconds"]}, sort_keys=True))
