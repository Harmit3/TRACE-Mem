"""Replay all frozen Memora development questions over resumable extracted claims."""

from argparse import ArgumentParser
from collections import Counter
from contextlib import closing
from dataclasses import asdict
from functools import lru_cache
import itertools
import json
from pathlib import Path
import re
import sqlite3
import time

from scripts.compare_local_verifiers import MODE, QWEN, SETTINGS, checksum, local_json
from scripts.extract_memora_full import DESIGN, input_history, restore, seed_cache
from scripts.run_memora import ARTIFACTS, ROOT, sha, write
from scripts.run_t2_development import frozen_rows
from scripts.updateset_v2_pilot import PROMPT_SCHEMA, QWEN_DIGEST
from trace_mem.adaptive_verification import AdaptiveAllocation, heuristic_score, neutralized_score
from trace_mem.baselines import _apply, _eligible_target
from trace_mem.claims import conflicts
from trace_mem.data.memora import replay
from trace_mem.features_v3 import CachedMiniLM, MINILM_REVISION, NLI_REVISION, V3Features, pinned_nli
from trace_mem.llm_tasks import DIRECT_V2_PROMPT, LLMTasks, RESPONSE_SCHEMAS
from trace_mem.memora_benchmark import METHODS, answer_suite, questions, run_suite
from trace_mem.memory import TemporalMemory
from trace_mem.providers import ChatProvider, ProviderConfig, ProviderError
from trace_mem.training import load_model


ENTITY = "development-persona"
ADAPTIVE = ("T2", "H-paced")
HISTORICAL_WORDING = re.compile(r"\b(previous(?:ly)?|formerly|used to|before|historical|past)\b", re.I)
EVENTLIKE = re.compile(r"expense|activity|event|appointment|task|steps|spend|purchase|visit|meeting|payment")


class TerminalResponseMemo:
    """Share terminal validation failures across identical replay requests."""

    TERMINAL = {
        "Provider response was incomplete or refused",
        "Provider response did not match the task schema",
    }

    def __init__(self, provider, database):
        self.provider = provider
        self.database = database
        with closing(sqlite3.connect(database)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS terminal (key TEXT PRIMARY KEY, error TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS reuse (id INTEGER PRIMARY KEY)")

    def generate(self, task, system, payload, validate):
        config = self.provider.config
        url, _, body = self.provider.request_for(config, task, system, payload)
        key = self.provider.cache_key(task, url, body)
        with closing(sqlite3.connect(self.database)) as db, db:
            error = db.execute("SELECT error FROM terminal WHERE key=?", (key,)).fetchone()
            if error:
                db.execute("INSERT INTO reuse DEFAULT VALUES")
            else:
                try:
                    return self.provider.generate(task, system, payload, validate)
                except ProviderError as exc:
                    if str(exc) not in self.TERMINAL:
                        raise
                    db.execute("INSERT INTO terminal VALUES (?, ?)", (key, str(exc)))
                    error = (str(exc),)
        raise ProviderError(error[0])

    def stats(self):
        with closing(sqlite3.connect(self.database)) as db:
            return {"distinct_terminal_failures": db.execute("SELECT COUNT(*) FROM terminal").fetchone()[0],
                    "failure_cache_hits": db.execute("SELECT COUNT(*) FROM reuse").fetchone()[0]}


def inspect_claims(prepared):
    """Count structural clashes on the unverified B2 reference trace."""
    memory = TemporalMemory()
    counts = Counter()
    categories = Counter()
    for item in prepared:
        claim, source = item.claim, item.source
        candidates = () if claim.intent == "delete" else conflicts(memory, ENTITY, claim)
        eligible = _eligible_target(memory, ENTITY, claim)
        counts["eligible"] += eligible is not None
        counts["any_conflict"] += bool(candidates)
        counts["same_effective_day"] += any(f.valid_from == claim.effective_on for f in candidates)
        counts["same_observation_day"] += any(f.source.observed_on == source.observed_on for f in candidates)
        counts["multiple_targets"] += len(candidates) > 1
        _apply(memory, ENTITY, claim, source, item.fact_id, "B2", None, None, None)
        operation = memory.trace[-1].operation
        counts[f"b2_{operation}"] += 1
        if candidates and operation == "defer" and EVENTLIKE.search(claim.predicate):
            counts["deferred_eventlike_clash"] += 1
            categories[claim.predicate] += 1
        if claim.intent == "delete":
            counts["delete_claims"] += 1
            counts["unresolved_delete"] += operation == "defer"
    return {"counts": dict(counts), "deferred_eventlike_predicates": dict(categories)}


def recover_extraction(repository, output, extraction_report):
    design, history, revision = input_history(repository)
    freeze = json.loads((output / "extraction-freeze.json").read_bytes())
    if (freeze["protocol_sha256"] != sha(DESIGN) or freeze["revision"] != revision
            or freeze["qwen"] != QWEN_DIGEST or freeze["provider_settings"] != SETTINGS):
        raise ValueError("Extraction does not match the frozen protocol")
    events = tuple(replay(history))
    sessions = list(dict.fromkeys(event.session_id for event in events))
    if len(sessions) != extraction_report["sessions"]:
        raise ValueError("The full extraction did not finish")
    paths = [output / "sessions" / f"{sid:04d}.json" for sid in sessions]
    prepared = tuple(restore(row) for path in paths for row in json.loads(path.read_bytes())["claims"])
    if len(prepared) != extraction_report["claims"]:
        raise ValueError("Session checkpoints disagree with the extraction report")
    chosen = questions(history / f"evaluation_questions_{history.name}.json", design["question_indices"])
    return design, revision, events, prepared, chosen, {p.name: sha(p) for p in paths}


def combinations(design, eligible):
    """Each closed-loop cap comes from the published nominal horizon."""
    nominal = design["closed_loop_budget_reference"]
    for mode, budget in itertools.product(("fixed", "closed-loop"), design["budgets_percent"]):
        cap = (eligible if mode == "fixed" else nominal) * budget // 100
        for seed in design["random_seeds"]:
            primary = seed == design["random_seeds"][0]
            methods = (*METHODS, *ADAPTIVE) if primary else ("B4",)
            yield mode, budget, cap, seed, design["primary_horizon"], methods
        if mode == "closed-loop":
            for horizon in design["horizon_sensitivity"]:
                if horizon != design["primary_horizon"]:
                    yield mode, budget, cap, design["random_seeds"][0], horizon, ADAPTIVE


def storage(memory, prepared, cutoff):
    days = {cutoff, *(c.claim.effective_on for c in prepared if c.claim.effective_on <= cutoff)}
    visible = memory.retrieve(ENTITY, None, as_of=cutoff)
    union = {f.fact_id: f for day in days for f in memory.retrieve(ENTITY, None, as_of=day)}
    size = sum(len(json.dumps(asdict(f), default=str, sort_keys=True).encode()) for f in union.values())
    return {"current_facts": len(visible), "historically_visible_unique_facts": len(union),
            "modeled_payload_bytes": size}


def make_adaptive(horizon, train, full):
    learned = lambda v: neutralized_score(full, v)
    return {name: AdaptiveAllocation(fn, tuple(sorted(map(fn, train))), horizon)
            for name, fn in (("T2", learned), ("H-paced", heuristic_score))}


def run(repository, output, outcomes, nli, reuse=None):
    import torch

    if (ROOT / "results").resolve() not in output.resolve().parents:
        raise ValueError("Use an ignored results directory")
    extraction = json.loads((output / "extraction-report.json").read_bytes())
    design, revision, events, prepared, chosen, hashes = recover_extraction(repository, output, extraction)
    artifacts = json.loads((ARTIFACTS / "fit-freeze.json").read_bytes())["artifacts_sha256"]
    if any(sha(ARTIFACTS / f) != checksum_ for f, checksum_ in artifacts.items()):
        raise ValueError("Frozen T1 artifacts changed")
    if ({m["name"]: m["digest"] for m in local_json("/api/tags")["models"]}.get(QWEN) != QWEN_DIGEST
            or checksum([DIRECT_V2_PROMPT, RESPONSE_SCHEMAS["verify-direct-v2"]]) != PROMPT_SCHEMA):
        raise ValueError("Local Qwen or verifier configuration changed")
    train = frozen_rows(outcomes)["train"]
    freeze = {"design": sha(DESIGN), "revision": revision, "extraction_hashes": hashes,
              "qwen": QWEN_DIGEST, "ollama": local_json("/api/version")["version"],
              "minilm": MINILM_REVISION, "nli": NLI_REVISION, "artifacts": artifacts,
              "verifier_schema": PROMPT_SCHEMA, "settings": SETTINGS, "training_source": sha(outcomes),
              "code": {str(f.relative_to(ROOT)): sha(f) for f in (
                  Path(__file__).resolve(), ROOT / "trace_mem/memora_benchmark.py",
                  ROOT / "trace_mem/adaptive_verification.py")}}
    frozen = output / "replay-freeze.json"
    if frozen.exists() and json.loads(frozen.read_bytes()) != freeze:
        raise ValueError("Replay configuration changed")
    write(frozen, freeze)
    checkpoints = output / "replay"
    checkpoints.mkdir(exist_ok=True)
    provider = ChatProvider(ProviderConfig("ollama", QWEN, design["max_replay_requests"], **SETTINGS),
                            output / "replay.sqlite")
    seed_cache(provider.database, reuse)
    memo = TerminalResponseMemo(provider, output / "replay-terminal.sqlite")
    tasks = LLMTasks(memo, verification_mode=MODE)
    started = time.perf_counter()
    torch.set_num_threads(4)
    embedding = CachedMiniLM()

    @lru_cache(maxsize=8192)
    def one_embedding(text):
        return tuple(embedding((text,))[0])

    def embed(texts):
        return [one_embedding(text) for text in texts]

    nli_model = pinned_nli(nli)
    features = V3Features(embed, lru_cache(maxsize=2048)(nli_model))
    without = V3Features(embed)
    models = {m: load_model(ARTIFACTS / f) for m, f in (
        ("T1", "full.json"), ("T1-no-NLI", "no_nli.json"))}
    builders = {"T1": features, "T1-no-NLI": without, "T2": features, "H-paced": without}
    checkpoints_read = []
    audit = inspect_claims(prepared)
    for cutoff in sorted({q.observed_on for q in chosen}):
        available_events = tuple(e for e in events if e.observed_on <= cutoff)
        available_claims = tuple(c for c in prepared if c.source.observed_on <= cutoff)
        candidates = inspect_claims(available_claims)["counts"].get("eligible", 0)
        upcoming = tuple(q for q in chosen if q.observed_on == cutoff)
        for mode, budget, cap, seed, horizon, methods in combinations(design, candidates):
            # Deduplicate identical caps (e.g. fixed 0% and 10% for short candidate streams).
            name = f"{cutoff}-{mode}-{cap}-{seed}-{horizon}.json"
            path = checkpoints / name
            if path.exists():
                rows = json.loads(path.read_bytes())
            else:
                policies = make_adaptive(horizon, train, models["T1"])
                states = run_suite(available_events, available_claims, tasks, entity=ENTITY, models=models,
                                   builders=builders, mode=mode, cap=cap, seed=seed,
                                   adaptive=policies, methods=methods)
                rows = []
                for q in upcoming:
                    answers = answer_suite(q, states, tasks, entity=ENTITY, k=design["retrieval_k"], embed=embed)
                    for m, entry in answers.items():
                        rows.append({"method": m, "question_id": q.identifier, "task": q.task,
                                     "cutoff": q.observed_on.isoformat(),
                                     "historical_wording": bool(HISTORICAL_WORDING.search(q.text)),
                                     "candidate_reference": candidates, **entry,
                                     **storage(states[m][0], available_claims, q.observed_on)})
                write(path, rows)
                print(json.dumps({"checkpoint": path.name, "predictions": len(rows)}), flush=True)
            checkpoints_read.extend({**row, "mode": mode, "requested_percent": budget,
                                     "seed": seed, "planning_horizon": horizon} for row in rows)
    write(output / "predictions.json", checkpoints_read)
    result = {"questions": len(chosen), "prediction_rows": len(checkpoints_read), "audit": audit,
              "provider": provider.stats(), **memo.stats(),
              "invocation_wall_seconds": time.perf_counter() - started}
    write(output / "replay-report.json", result)
    return result


if __name__ == "__main__":
    p = ArgumentParser(description=__doc__)
    p.add_argument("memora", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--outcomes", type=Path, required=True)
    p.add_argument("--nli", type=Path, required=True)
    p.add_argument("--reuse", type=Path)
    a = p.parse_args()
    print(json.dumps(run(a.memora, a.output, a.outcomes, a.nli, a.reuse), sort_keys=True))
