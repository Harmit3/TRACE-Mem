"""Checkpointed, frozen Step 30 evaluation with policy-constrained evidence."""

from argparse import ArgumentParser
from collections import Counter, defaultdict
from dataclasses import asdict, replace
from functools import lru_cache
import hashlib
import itertools
import json
from pathlib import Path
import time

from scripts.compare_local_verifiers import MODE, QWEN, SETTINGS, checksum, local_json
from scripts.replay_memora_full import TerminalResponseMemo, make_adaptive
from scripts.run_memora import ARTIFACTS, ROOT, sha, write
from scripts.run_t2_development import frozen_rows
from scripts.step30_dataset import generate
from scripts.updateset_v2_pilot import PROMPT_SCHEMA, QWEN_DIGEST
from trace_mem.baselines import _apply, _eligible_target
from trace_mem.evidence_index_v2 import EvidenceIndexV2, Field
from trace_mem.features_v3 import CachedMiniLM, MINILM_REVISION, NLI_REVISION, V3Features, pinned_nli
from trace_mem.llm_tasks import DIRECT_V2_PROMPT, LLMTasks, RESPONSE_SCHEMAS
from trace_mem.memora_benchmark import METHODS, Question, run_suite
from trace_mem.memory import TemporalMemory
from trace_mem.providers import ChatProvider, LimitExceeded, ProviderConfig, ProviderError
from trace_mem.reader_v2 import BUDGETS, read
from trace_mem.retrieval_diagnostic import trim
from trace_mem.training import load_model


DESIGN = ROOT / "docs/step30_freeze.json"
SYSTEMS = (*METHODS, "T2", "H-paced")
ENTITY = "fictional-history"


def dataset_hash(histories):
    rows = [{**{k: v for k, v in h.items() if k not in ("events", "claims")},
             "events": [asdict(e) for e in h["events"]],
             "claims": [asdict(c) for c in h["claims"]]} for h in histories]
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


def apply(memory, item):
    _apply(memory, ENTITY, item.claim, item.source, item.fact_id, "B2", None, None, None)


def validate_reference(history):
    reference = TemporalMemory()
    eligible = []
    for item in history["claims"]:
        if _eligible_target(reference, ENTITY, item.claim) is not None:
            eligible.append(item.fact_id)
        apply(reference, item)
    if eligible != list(history["decisions"]):
        raise ValueError(f"Frozen eligibility disagrees for {history['id']}")
    return len(eligible)


def cap_for(percent, history_index):
    # Rotate the fractional residual over the frozen order, without inspecting outcomes.
    return ((history_index + 1) * 5 * percent // 100 - history_index * 5 * percent // 100)


def oracle(history):
    memory = TemporalMemory()
    for item in history["claims"]:
        if item.fact_id in history["decisions"]:
            if not history["decisions"][item.fact_id]["changed"]:
                continue
            item = replace(item, claim=replace(item.claim, intent="correct"))
        apply(memory, item)
    return memory


def project(memory, history, day):
    """No raw-event fallback. The privacy target is denied even on historical queries."""
    retained = memory.retrieve(ENTITY, None, as_of=day)
    return tuple(Field(f.fact_id, f.source.reference, f.value, f.predicate, f.source.observed_on,
                       f.valid_from, f.valid_to) for f in retained
                 if f.predicate != "private note" and history["private"] not in f.value
                 and f.source.observed_on <= day)


def memory_metrics(memory, history):
    pred = history["predicate"]
    checks = tuple(history["decisions"].values())
    at = lambda day: {f.value for f in memory.retrieve(ENTITY, pred, as_of=day)}
    current = sum(at(check["day"]) == {check["expected"]} for check in checks)
    current += at(history["final"]) == {history["current"]}
    historical = (at(history["start"]) == {history["initial"]}) + sum(
        at(check["day"]) == {check["expected"]} for check in checks[:-1])
    raw_deleted = sum(not memory.retrieve(ENTITY, "private note", as_of=day)
                      for day in (history["start"], history["final"]))
    gate = 0
    for day in (history["start"], history["final"]):
        fields = project(memory, history, day)
        index = EvidenceIndexV2(fields, "frozen-public-synthetic")
        embedded = []
        def probe(texts):
            embedded.extend(texts[1:])
            return [[1, 0] for _ in texts]
        handle = index.retrieve("previous routing information", day, probe, k=len(fields))
        all_facts = index.materialize(handle, ENTITY)
        gate += not any(history["private"] in f.value for f in all_facts) and not any(
            history["private"] in value for value in embedded)
    return {"current": current, "current_total": 6, "historical": historical, "historical_total": 5,
            "deletion": raw_deleted, "deletion_total": 2, "authorized_deletion": gate,
            "harmful_adoptions": sum(check["proposal"] in at(check["day"]) for check in checks
                                     if not check["changed"])}


def qa(memory, history, embed, providers):
    fields = project(memory, history, history["final"])
    index = EvidenceIndexV2(fields, "frozen-public-synthetic")
    result = {}
    for mode, question, expected in (
        ("short", f"What is the current {history['predicate']}?", history["current"]),
        ("reasoning", "What was the total spending in these records?", f"${history['cost']}.00"),
    ):
        query = Question("synthetic", mode, question, history["final"])
        handle = index.retrieve(question, query.as_of, embed, k=8)
        facts = trim(query, index.materialize(handle, ENTITY), 3000, 8)
        try:
            answer = read(providers[mode], question, facts, as_of=query.as_of, mode=mode).answer
            text, error = answer.text, False
        except LimitExceeded:
            raise
        except ProviderError:
            text, error = None, True
        result[mode] = {"correct": bool(text and expected.casefold() in text.casefold()),
                        "abstained": text is None and not error, "error": error}
    return result


def evaluate_history(history, index, config, tasks, models, builders, adaptive, embed, readers):
    reference = validate_reference(history)
    rows = []
    for mode, percent in itertools.product(("fixed", "closed-loop"), config["budget_percents"]):
        cap = cap_for(percent, index)
        for seed in config["seeds"]:
            primary = seed == config["seeds"][0]
            counts = defaultdict(Counter)
            def observer(method, item, target, verdict, applied, failed):
                if not applied or failed:
                    return
                gold = history["decisions"][item.fact_id]["expected"]
                without = item.claim.value if item.claim.intent == "correct" else target.value
                with_call = item.claim.value if verdict == "update" else target.value
                counts[method]["helpful_verifications"] += without != gold and with_call == gold
                counts[method]["harmful_verifications"] += without == gold and with_call != gold
            outcomes = run_suite(history["events"], history["claims"], tasks, entity=ENTITY,
                                 models=models, builders=builders, mode=mode, cap=cap, seed=seed,
                                 adaptive=adaptive, methods=SYSTEMS if primary else ("B4",),
                                 observer=observer)
            for method, (memory, stats) in outcomes.items():
                measured = memory_metrics(memory, history)
                if measured["authorized_deletion"] != 2:
                    raise ValueError("Authorized evidence exposed a restricted field")
                row = {"method": method, "mode": mode, "budget": percent, "seed": seed,
                       "reference_candidates": reference, **stats, **measured,
                       "helpful_verifications": counts[method]["helpful_verifications"],
                       "harmful_verifications": counts[method]["harmful_verifications"]}
                if percent == 50 and history["member"] == 0:
                    row["qa"] = qa(memory, history, embed, readers)
                rows.append(row)
    ceiling = oracle(history)
    result = {"history": history["id"], "family": history["family"], "rows": rows,
              "oracle": memory_metrics(ceiling, history)}
    if history["member"] == 0:
        result["oracle_qa"] = qa(ceiling, history, embed, readers)
    return result


def run(outcomes, nli, output):
    import torch

    if (ROOT / "results").resolve() not in output.resolve().parents:
        raise ValueError("Use an ignored results directory")
    config = json.loads(DESIGN.read_bytes())
    histories = list(generate(config))
    digest = dataset_hash(histories)
    if digest != config["dataset_sha256"] or sum(map(validate_reference, histories)) != 500:
        raise ValueError("Frozen dataset or eligibility changed")
    tags = {row["name"]: row["digest"] for row in local_json("/api/tags")["models"]}
    if tags.get(QWEN) != QWEN_DIGEST or checksum(
            [DIRECT_V2_PROMPT, RESPONSE_SCHEMAS["verify-direct-v2"]]) != PROMPT_SCHEMA:
        raise ValueError("Pinned verifier identity or prompt changed")
    artifacts = json.loads((ARTIFACTS / "fit-freeze.json").read_bytes())["artifacts_sha256"]
    if any(sha(ARTIFACTS / key) != value for key, value in artifacts.items()):
        raise ValueError("Frozen controller artifacts changed")
    output.mkdir(parents=True, exist_ok=True)
    directory = output / "histories"
    directory.mkdir(exist_ok=True)
    manifest = {"protocol": sha(DESIGN), "dataset": digest, "artifacts": artifacts, "qwen": QWEN_DIGEST,
                "minilm": MINILM_REVISION, "nli": NLI_REVISION, "settings": SETTINGS,
                "training_features": sha(outcomes), "code": sha(Path(__file__))}
    path = output / "freeze.json"
    if path.exists() and json.loads(path.read_bytes()) != manifest:
        raise ValueError("Cannot resume a changed run")
    write(path, manifest)
    started = time.perf_counter()
    torch.set_num_threads(4)
    model = CachedMiniLM()
    vectors = {}
    def embed(values):
        missing = list(dict.fromkeys(t for t in values if t not in vectors))
        for i in range(0, len(missing), 32):
            batch = missing[i:i+32]
            vectors.update(zip(batch, model(batch), strict=True))
        return [vectors[t] for t in values]
    features = V3Features(embed, lru_cache(maxsize=2048)(pinned_nli(nli)))
    without = V3Features(embed)
    models = {m: load_model(ARTIFACTS / filename) for m, filename in (
        ("T1", "full.json"), ("T1-no-NLI", "no_nli.json"))}
    builders = {"T1": features, "T1-no-NLI": without, "T2": features, "H-paced": without}
    adaptive = make_adaptive(config["nominal_opportunities"], frozen_rows(outcomes)["train"], models["T1"])
    verifier = ChatProvider(ProviderConfig("ollama", QWEN, config["max_verifier_requests"], **SETTINGS),
                            output / "verifier.sqlite")
    tasks = LLMTasks(TerminalResponseMemo(verifier, output / "verifier-terminal.sqlite"), verification_mode=MODE)
    backends = {mode: ChatProvider(ProviderConfig("ollama", QWEN, config["max_reader_requests"],
                 **(SETTINGS | {"max_output_tokens": BUDGETS[mode]})), output / f"reader-{mode}.sqlite")
                for mode in ("short", "reasoning")}
    readers = {mode: TerminalResponseMemo(provider, output / f"reader-terminal-{mode}.sqlite")
               for mode, provider in backends.items()}
    completed = []
    for n, history in enumerate(histories):
        path = directory / f"{n:03d}.json"
        if path.exists():
            row = json.loads(path.read_bytes())
        else:
            row = evaluate_history(history, n, config, tasks, models, builders, adaptive, embed, readers)
            write(path, row)
        completed.append(row)
        if (n + 1) % 5 == 0:
            print(json.dumps({"completed": n + 1, "verifier": verifier.stats()}), flush=True)
    report = {"completed": len(completed), "families": len({h["family"] for h in completed}),
              "reference_candidates": sum(map(validate_reference, histories)),
              "verifier": verifier.stats(), "reader": {k: p.stats() for k, p in backends.items()},
              "wall_seconds": time.perf_counter() - started, "histories": completed}
    write(output / "report.json", report)
    return {k: v for k, v in report.items() if k != "histories"}


if __name__ == "__main__":
    p = ArgumentParser(description=__doc__)
    for arg in ("outcomes", "nli", "output"):
        p.add_argument(arg, type=Path)
    args = p.parse_args()
    print(json.dumps(run(args.outcomes, args.nli, args.output), sort_keys=True))
