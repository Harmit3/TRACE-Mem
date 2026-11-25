"""Controlled, source-grounded development diagnostic with frozen T1 policies."""

from argparse import ArgumentParser
from collections import Counter
from datetime import date
import itertools
import json
from pathlib import Path
import time

from scripts.compare_local_verifiers import MODE, QWEN, SETTINGS, checksum, local_json
from scripts.run_memora import ARTIFACTS, PROTOCOL, ROOT, audit_checkout, sha, write
from scripts.updateset_v2_pilot import PROMPT_SCHEMA, QWEN_DIGEST
from trace_mem.baselines import PreparedClaim
from trace_mem.claims import Claim
from trace_mem.data.memora import Event, replay
from trace_mem.features_v3 import CachedMiniLM, MINILM_REVISION, NLI_REVISION, V3Features, pinned_nli
from trace_mem.llm_tasks import DIRECT_V2_PROMPT, LLMTasks, RESPONSE_SCHEMAS
from trace_mem.memora_benchmark import Question, answer_suite, prepare, questions, run_suite
from trace_mem.memory import Source
from trace_mem.providers import ChatProvider, ProviderConfig
from trace_mem.training import load_model


DESIGN = ROOT / "docs/memora_step22_freeze.json"
FIXED_DAY = date(2025, 3, 1)
NEXT_DAY = date(2025, 3, 2)


def source_claim(event, predicate, value, intent):
    if event.role != "user" or not isinstance(value, str) or not value or value not in event.message:
        raise ValueError("Oracle candidate must cite a verbatim value in a focal user message")
    origin = f"{event.session_id}/{event.turn}"
    return PreparedClaim(Claim(predicate, value, intent, event.observed_on),
                         Source(event.observed_on, origin, event.source_kind), f"{origin}/0")


def bound_sessions(events, count):
    return tuple(event for _, rows in itertools.islice(
        itertools.groupby(events, key=lambda event: event.session_id), count) for event in rows)


def dev_input(source, config):
    upstream = json.loads(PROTOCOL.read_bytes())
    audit_checkout(source, upstream)
    dev = upstream["development"]
    history = source / dev["path"]
    events = bound_sessions(replay(history), config["sessions"])
    index = {(e.session_id, e.turn): e for e in events}
    spans = tuple(source_claim(index[s, t], predicate, value, intent)
                  for s, t, predicate, value, intent in config["memora_spans"])
    pending = {(s, t): issue for s, t, issue in config["pending"]}
    labels = {(s, t): {"predicate": p, "value": v, "intent": i}
              for s, t, p, v, i in config["memora_spans"]}
    packet = [{"session": e.session_id, "turn": e.turn, "day": e.observed_on.isoformat(),
               "speaker": e.role, "text": e.message, "source_id": f"{e.session_id}/{e.turn}",
               "proposed_claim": labels.get((e.session_id, e.turn)),
               "review_note": pending.get((e.session_id, e.turn)),
               "human_review": "pending"}
              for e in events]
    return events, spans, packet, questions(history / f"evaluation_questions_{history.name}.json", dev["selectors"])


def synthetic_input(fixture):
    examples = []
    wants = []
    for p, old, new, intent, statement, updated in fixture["pairs"]:
        examples.append((FIXED_DAY, p, old, "assert", f"Please remember my {p} is {old}."))
        examples.append((NEXT_DAY, p, new, intent, statement))
        wants.extend([(p, old, FIXED_DAY, True, "historical"),
                      (p, new if updated else old, NEXT_DAY, True, "current"),
                      (p, old if updated else new, NEXT_DAY, False, "current")])
    p, v = fixture["deleted"]
    examples.extend([(FIXED_DAY, p, v, "assert", f"Please remember my {p} is {v}."),
                     (NEXT_DAY, p, v, "delete", f"Please delete my {p}: {v}.")])
    wants.extend([(p, v, FIXED_DAY, False, "deletion"), (p, v, NEXT_DAY, False, "deletion")])
    events = tuple(Event(day, n, 1, "user", text) for n, (day, _, _, _, text)
                   in enumerate(sorted(examples, key=lambda row: row[0]), 1))
    prepared = tuple(source_claim(e, predicate, value, intent)
                     for e, (_, predicate, value, intent, _) in
                     zip(events, sorted(examples, key=lambda row: row[0])))
    q = Question(fixture["id"], "synthetic", fixture["question"], NEXT_DAY)
    expected_answer, = [value for pred, value, _, present, group in wants
                        if pred == fixture["answer_predicate"] and present and group == "current"]
    return events, prepared, tuple(wants), (q,), expected_answer


def assess(memory, entity, current, expected, prepared):
    outcomes = {}
    for p, v, day, present, group in expected:
        state = memory.retrieve(entity, p, as_of=day)
        present_now = any(f.value.casefold() == v.casefold() for f in state)
        counter = outcomes.setdefault(group, Counter())
        counter["total"] += 1
        counter["correct"] += present_now == present
    grounded = {(p.claim.predicate, p.claim.value.casefold()) for p in prepared
                if p.claim.intent != "delete"}
    visible = {(f.predicate, f.value.casefold()) for f in memory.retrieve(entity, None, as_of=current)}
    return {"checks": {group: dict(row) for group, row in outcomes.items()},
            "visible_facts": len(visible), "visible_outside_oracle": len(visible - grounded)}


def study(events, oracle, expectations, queries, expected_answer, tasks, models, builders, embed, config):
    automatic, errors = prepare(events, tasks)
    entity = "development_persona"
    results, predictions = [], {}
    for condition, claims in (("automatic", automatic), ("span-oracle", oracle)):
        initial = run_suite(events, claims, tasks, entity=entity, models=models,
                            builders=builders, mode="fixed", cap=0, seed=config["seed"])
        count = initial["B2"][1]["eligible_candidates"]
        memo = {}
        for mode, percent in itertools.product(("fixed", "closed-loop"), config["budgets"]):
            cap = count * percent // 100
            if (mode, cap) not in memo:
                states = run_suite(events, claims, tasks, entity=entity, models=models,
                                   builders=builders, mode=mode, cap=cap, seed=config["seed"])
                answers = {q.identifier: answer_suite(q, states, tasks, entity=entity, k=config["k"],
                                                       embed=embed) for q in queries}
                memo[mode, cap] = states, answers
            states, answers = memo[mode, cap]
            for method, (memory, stats) in states.items():
                for q in queries:
                    entry = answers[q.identifier][method]
                    row = {"condition": condition, "mode": mode, "method": method,
                           "requested_percent": percent, "reference_candidates": count, **stats,
                           "actual_reference_coverage": stats["verification_attempts"] / count if count else None,
                           "abstained": entry["answer"] is None, "reader_error": entry["reader_error"],
                           "answer_expected_literal": (expected_answer.casefold() in
                               (entry["answer"] or "").casefold()) if expected_answer else None,
                           **assess(memory, entity, q.observed_on, expectations, oracle)}
                    results.append(row)
                    if percent == 100:
                        predictions.setdefault(condition, []).append(
                            {"question_id": q.identifier, "task": q.task, "mode": mode,
                             "method": method, **entry})
        if condition == "automatic":
            counts = {"emitted": len(automatic), "turns_with_claims": len({p.source.reference for p in automatic})}
    return {"rows": results, "automatic": counts, "oracle_claims": len(oracle),
            "extraction_failures": errors, "events": len(events),
            "user_turns": sum(e.role == "user" for e in events)}, predictions


def run(source, nli, output, *, packet_only=False):
    if (ROOT / "results").resolve() not in output.resolve().parents:
        raise ValueError("Keep review packets and predictions under ignored results/")
    config = json.loads(DESIGN.read_bytes())
    events, spans, packet, chosen = dev_input(source, config)
    output.mkdir(parents=True, exist_ok=True)
    write(output / "review-packet.json", packet)
    if packet_only:
        return {"review_rows": len(packet), "literal_span_candidates": len(spans),
                "explicit_review_questions": len(config["pending"])}
    import torch

    fit = json.loads((ARTIFACTS / "fit-freeze.json").read_bytes())
    if any(sha(ARTIFACTS / file) != value for file, value in fit["artifacts_sha256"].items()):
        raise ValueError("Frozen controller artifact mismatch")
    tags = {item["name"]: item["digest"] for item in local_json("/api/tags")["models"]}
    if tags.get(QWEN) != QWEN_DIGEST or checksum(
            [DIRECT_V2_PROMPT, RESPONSE_SCHEMAS["verify-direct-v2"]]) != PROMPT_SCHEMA:
        raise ValueError("Pinned model or direct-v2 verifier changed")
    freeze = {"design_sha256": sha(DESIGN), "source_protocol_sha256": sha(PROTOCOL),
              "model_artifacts": fit["artifacts_sha256"], "qwen": QWEN_DIGEST, "settings": SETTINGS,
              "minilm": MINILM_REVISION, "nli": NLI_REVISION,
              "ollama": local_json("/api/version")["version"], "runner_sha256": sha(Path(__file__))}
    path = output / "freeze.json"
    if path.exists() and json.loads(path.read_bytes()) != freeze:
        raise ValueError("Use a new directory for a changed study configuration")
    write(path, freeze)
    torch.set_num_threads(4)
    embed = CachedMiniLM()
    builders = {"T1": V3Features(embed, pinned_nli(nli)), "T1-no-NLI": V3Features(embed)}
    models = {m: load_model(ARTIFACTS / file) for m, file in (
        ("T1", "full.json"), ("T1-no-NLI", "no_nli.json"))}
    provider = ChatProvider(ProviderConfig("ollama", QWEN, 400, **SETTINGS), output / "responses.sqlite")
    tasks = LLMTasks(provider, verification_mode=MODE)
    started = time.perf_counter()
    # These are verified literal-span coverage checks, rather than independently reviewed memory gold.
    relevant = tuple((p.claim.predicate, p.claim.value, chosen[0].observed_on, True, "literal_span")
                     for p in spans)
    data, predictions = study(events, spans, relevant, chosen, None, tasks, models, builders, embed, config)
    for condition, rows in predictions.items():
        write(output / f"predictions-{condition}.json", rows)
    result = {"memora_prefix": data, "fictional": {}}
    for fixture in config["synthetic"]:
        diagnostic, _ = study(*synthetic_input(fixture), tasks, models, builders, embed, config)
        result["fictional"][fixture["id"]] = diagnostic
    result.update(provider=provider.stats(), wall_seconds=time.perf_counter() - started)
    write(output / "report.json", result)
    return {"memora_user_turns": data["user_turns"], "automatic": data["automatic"],
            "oracle_claims": data["oracle_claims"], "provider": result["provider"],
            "wall_seconds": result["wall_seconds"]}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--nli", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--packet-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.source, args.nli, args.output, packet_only=args.packet_only), sort_keys=True))
