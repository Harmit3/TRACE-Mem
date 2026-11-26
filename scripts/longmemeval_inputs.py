"""Metadata-only sampling and allowlisted LongMemEval model inputs."""

from argparse import ArgumentParser
from datetime import datetime
import json
from pathlib import Path
import random

from scripts.run_memora import ROOT, sha, write
from trace_mem.data.memora import Event

DESIGN = ROOT / "docs/step32_freeze.json"
TYPES = ("single-session-user", "single-session-assistant", "single-session-preference",
         "multi-session", "temporal-reasoning", "knowledge-update")


def choose(records, seed):
    rng = random.Random(seed)
    pools = {kind: [] for kind in (*TYPES, "abstention")}
    for row in records:
        key = row["question_id"]
        pools["abstention" if "_abs" in key else row["question_type"]].append(key)
    pairs = [rng.sample(sorted(pools[kind]), 2) for kind in TYPES]
    return [ids[round_] for round_ in range(2) for ids in pairs] + rng.sample(
        sorted(pools["abstention"]), 2)


def timestamp(text):
    return datetime.strptime(text, "%Y/%m/%d (%a) %H:%M")


def project(record, alias):
    cutoff = timestamp(record["question_date"])
    result = []
    for ordinal, (date, session) in enumerate(zip(
        record["haystack_dates"], record["haystack_sessions"], strict=True
    ), 1):
        when = timestamp(date)
        if when > cutoff:
            continue
        for turn, message in enumerate(session, 1):
            if message["role"] not in ("user", "assistant") or not isinstance(message["content"], str):
                raise ValueError("Unexpected LongMemEval message")
            result.append((when, ordinal, turn, message["role"], message["content"]))
    return {"case": alias, "question": record["question"], "day": cutoff.date().isoformat(),
            "turns": [[when.date().isoformat(), sid, n, role, content]
                      for when, sid, n, role, content in sorted(result)]}


def events(case):
    return tuple(Event(datetime.fromisoformat(day).date(), sid, turn, role, content)
                 for day, sid, turn, role, content in case["turns"])


def prepare(dataset, output):
    if (ROOT / "results").resolve() not in output.resolve().parents:
        raise ValueError("Use an ignored results directory")
    design = json.loads(DESIGN.read_bytes())
    if sha(dataset) != design["dataset_sha256"]:
        raise ValueError("Unexpected LongMemEval dataset bytes")
    dataset = json.loads(dataset.read_bytes())
    if len(dataset) != 500:
        raise ValueError("Unexpected dataset size")
    selected = choose(dataset, design["seed"])
    if "selected" in design and selected != design["selected"]:
        raise ValueError("Sample changed")
    records = {row["question_id"]: row for row in dataset}
    cases = [project(records[qid], f"L{i:02d}") for i, qid in enumerate(selected, 1)]
    output.mkdir(parents=True, exist_ok=True)
    write(output / "inputs.json", cases)
    print(json.dumps({"selected": selected, "by_case": [{
        "case": c["case"], "turns": len(c["turns"]),
        "user_turns": sum(t[3] == "user" for t in c["turns"])} for c in cases]}))


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    prepare(args.dataset, args.output)
