"""Diagnose full-development retrieval without providing rubric labels to the reader."""

from argparse import ArgumentParser
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date
from functools import lru_cache
import json
from pathlib import Path
import sqlite3
import time

from scripts.compare_local_verifiers import MODE, QWEN, SETTINGS, local_json
from scripts.extract_memora_full import seed_cache
from scripts.replay_memora_full import ENTITY, make_adaptive, recover_extraction, TerminalResponseMemo
from scripts.run_memora import ARTIFACTS, ROOT, sha, write
from scripts.run_t2_development import frozen_rows
from scripts.updateset_v2_pilot import QWEN_DIGEST
from scripts.validate_ollama_verifier import DIGEST as LLAMA_DIGEST, MODEL as LLAMA
from trace_mem.features_v3 import CachedMiniLM, V3Features, pinned_nli
from trace_mem.llm_tasks import LLMTasks
from trace_mem.local_rubric import judge
from trace_mem.memory import Fact, Source
from trace_mem.memora_benchmark import answer_suite, run_suite
from trace_mem.providers import ChatProvider, LimitExceeded, ProviderConfig, ProviderError, http_transport
from trace_mem.retrieval_diagnostic import candidate_event, evidence_metrics, in_scope, ranked_sources, trim
from trace_mem.semantic import retrieve_semantic
from trace_mem.training import load_model


DESIGN = ROOT / "docs/memora_step25_freeze.json"
PRIOR = "13698739ac3735a4c0b1182f86f095d591fec3cbb1e6ddb73370bf34d16e5573"


class OfflineReplay:
    """Reconstruct the inputs behind historical errors without new inference."""
    def __init__(self, responses, terminals, config):
        self.responses = responses
        self.terminals = terminals
        self.config = config
        self.inputs = {}
        self.current = None

    def generate(self, task, system, payload, validate):
        url, _, body = ChatProvider.request_for(self.config, task, system, payload)
        key = ChatProvider.cache_key(task, url, body)
        if key in self.terminals:
            self.inputs[key] = (self.current, self.terminals[key])
            raise ProviderError(self.terminals[key])
        if key not in self.responses:
            raise RuntimeError(f"No historical cached {task} request for the reconstructed state")
        result = self.responses[key]
        validate(result)
        return result


def sqlite_values(path, sql):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        return dict(db.execute(sql))


def reconstruct(prior, events, prepared, chosen, frozen, builders, models, train, embed):
    config = ProviderConfig("ollama", QWEN, 2400, **SETTINGS)
    offline = OfflineReplay(sqlite_values(prior / "replay.sqlite", "SELECT key,text FROM response"),
                            sqlite_values(prior / "replay-terminal.sqlite", "SELECT key,error FROM terminal"),
                            config)
    groups = defaultdict(list)
    for row in frozen:
        if row["reader_error"]:
            groups[(row["mode"], row["budget_cap"], row["seed"], row["planning_horizon"],
                    row["method"])].append(row)
    index = {q.identifier: q for q in chosen}
    for (mode, cap, seed, horizon, method), failures in groups.items():
        states = run_suite(events, prepared, LLMTasks(offline, verification_mode=MODE), entity=ENTITY,
                           models=models, builders=builders, mode=mode, cap=cap, seed=seed,
                           adaptive=make_adaptive(horizon, train, models["T1"]), methods=(method,))
        for row in failures:
            q = index[row["question_id"]]
            state = states[method][0]
            hits = retrieve_semantic(state, q.text, entity=ENTITY, as_of=q.as_of, k=8, embed=embed)
            facts = trim(q, (h.fact for h in hits), 3000, 8)
            offline.current = q, facts
            answer_suite(q, states, LLMTasks(offline), entity=ENTITY, k=8, embed=embed)
        if set(offline.inputs) == set(offline.terminals):
            break
    return offline.inputs


def response_snapshot(raw):
    payload = raw.get("message", {}).get("content", "")
    detail = {"done_reason": raw.get("done_reason"), "output_tokens": raw.get("eval_count"),
              "json_object": False, "keys_valid": False, "citations_are_list": False}
    try:
        obj = json.loads(payload)
    except (ValueError, TypeError):
        return detail
    if isinstance(obj, dict):
        detail.update(json_object=True, keys_valid=set(obj) == {"answer", "citations"},
                      citations_are_list=isinstance(obj.get("citations"), list))
        if isinstance(obj.get("citations"), list):
            detail["citations"] = obj["citations"]
            detail["duplicates"] = len({str(x) for x in obj["citations"]}) < len(obj["citations"])
    return detail


def run(source, prior, output, nli, outcomes):
    import torch

    if (ROOT / "results").resolve() not in output.resolve().parents:
        raise ValueError("Use a local ignored results directory")
    spec = json.loads(DESIGN.read_bytes())
    if sha(prior / "predictions.json") != PRIOR:
        raise ValueError("Use the exact published Step 24 prediction stream")
    extraction = json.loads((prior / "extraction-report.json").read_bytes())
    _, revision, events, prepared, chosen, _ = recover_extraction(source, prior, extraction)
    if len(chosen) != len(spec["questions"]) or len({q.observed_on for q in chosen}) != 1:
        raise ValueError("Unexpected frozen question population")
    tags = {m["name"]: m["digest"] for m in local_json("/api/tags")["models"]}
    if tags.get(QWEN) != QWEN_DIGEST or tags.get(LLAMA) != LLAMA_DIGEST:
        raise ValueError("Pinned reader and judge models are required")
    artifacts = json.loads((ARTIFACTS / "fit-freeze.json").read_bytes())["artifacts_sha256"]
    if any(sha(ARTIFACTS / f) != digest for f, digest in artifacts.items()):
        raise ValueError("Frozen artifacts changed")
    output.mkdir(parents=True, exist_ok=True)
    freeze = {"design_sha256": sha(DESIGN), "prior_predictions_sha256": PRIOR,
              "revision": revision, "qwen": QWEN_DIGEST, "llama": LLAMA_DIGEST,
              "settings": SETTINGS, "code_sha256": sha(Path(__file__))}
    manifest = output / "freeze.json"
    if manifest.exists() and json.loads(manifest.read_bytes()) != freeze:
        raise ValueError("Diagnostic configuration changed")
    write(manifest, freeze)
    started = time.perf_counter()
    torch.set_num_threads(4)
    mini = CachedMiniLM()

    @lru_cache(maxsize=8192)
    def one(text):
        return tuple(mini((text,))[0])

    def embed(values):
        return [one(x) for x in values]

    nli_model = pinned_nli(nli)
    features = V3Features(embed, lru_cache(maxsize=2048)(nli_model))
    without = V3Features(embed)
    builders = {"T1": features, "T1-no-NLI": without, "T2": features, "H-paced": without}
    models = {m: load_model(ARTIFACTS / f) for m, f in (
        ("T1", "full.json"), ("T1-no-NLI", "no_nli.json"))}
    train = frozen_rows(outcomes)["train"]
    old = json.loads((prior / "predictions.json").read_bytes())
    events = tuple(e for e in events if e.observed_on <= chosen[0].observed_on)
    prepared = tuple(item for item in prepared if item.source.observed_on <= chosen[0].observed_on)
    errors = reconstruct(prior, events, prepared, chosen, old, builders, models, train, embed)
    observed_responses = []

    def transport(*args):
        response = http_transport(*args)
        observed_responses.append(response_snapshot(response))
        return response

    backend = ChatProvider(ProviderConfig("ollama", QWEN, spec["max_reader_requests"], **SETTINGS),
                           output / "reader.sqlite", transport=transport)
    seed_cache(backend.database, prior / "replay.sqlite")
    tasks = LLMTasks(TerminalResponseMemo(backend, output / "reader-terminal.sqlite"))
    terminal = []
    # These exact historical requests are rerun rather than seeded from invalid outcomes.
    probe_backend = ChatProvider(ProviderConfig("ollama", QWEN, 10, **SETTINGS),
                                 output / "error-probe.sqlite", transport=transport)
    probe_tasks = LLMTasks(probe_backend)
    for key, ((q, facts), original) in errors.items():
        first = len(observed_responses)
        row = {"request_key": key, "question": q.identifier, "historical_error": original}
        try:
            response = probe_tasks.answer_from_facts(q.text, facts, as_of=q.as_of)
            row["rerun"] = "abstained" if response.text is None else "answered"
        except ProviderError as exc:
            row["rerun"] = str(exc)
        if len(observed_responses) > first:
            detail = observed_responses[-1].copy()
            if "citations" in detail:
                ids = {f.fact_id for f in facts}
                detail["unknown_citation_count"] = sum(
                    not isinstance(x, str) or x not in ids for x in detail.pop("citations"))
            row["response"] = detail
        terminal.append(row)
    write(output / "terminal-analysis.json", terminal)
    print(f"Reconstructed {len(terminal)} terminal requests", flush=True)

    memory, _ = run_suite(events, prepared, tasks, entity=ENTITY, models={}, builders={},
                          mode="closed-loop", cap=0, seed=7, methods=("B2",))["B2"]
    event_index = {f"{event.session_id}/{event.turn}": event for event in events}
    rows, packet, validation = [], [], []
    emitted = {item.source.reference for item in prepared}
    for i, (q, rule) in enumerate(zip(chosen, spec["questions"]), 1):
        references = rule["spans"]
        if len(set(references)) != len(references) or not all(
                key in event_index and in_scope(event_index[key], q.as_of, spec) for key in references):
            raise ValueError(f"Ineligible source reference in question {i}")
        visible = {fact.source.reference for fact in memory.retrieve(ENTITY, None, as_of=q.as_of)}
        planned = [candidate_event(event_index[ref], ENTITY) for ref in references]
        representations = {
            "structured-b2": [h.fact for h in retrieve_semantic(
                memory, q.text, entity=ENTITY, as_of=q.as_of, k=spec["k"], embed=embed)],
            "transcript-diagnostic": ranked_sources(q, events, spec, embed, ENTITY),
            "source-oracle-diagnostic": planned,
        }
        case = {"number": i, "question": q.text, "date": q.observed_on.isoformat(),
                "source_candidates": [{"source": ref, "text": event_index[ref].message} for ref in references],
                "review": rule["review"], "human_review": "pending", "comparisons": []}
        for mode, facts in representations.items():
            retained = trim(q, facts, spec["evidence_bytes"], spec["k"])
            stats = evidence_metrics(references, emitted, visible, retained)
            row = {"number": i, "question_id": q.identifier, "task": q.task, "mode": mode,
                   **stats, "context_fact_count": len(retained),
                   "context_payload_bytes": len(json.dumps([f.value for f in retained]).encode())}
            try:
                answer = tasks.answer_from_facts(q.text, retained, as_of=q.as_of)
                row.update(answer=answer.text, citations=answer.citations, error=None)
            except LimitExceeded:
                raise
            except ProviderError as exc:
                row.update(answer=None, citations=(), error=str(exc))
            rows.append(row)
            case["comparisons"].append({"mode": mode, "retained_sources": [f.source.reference for f in retained],
                                        "answer": row["answer"], "reader_error": row["error"]})
        packet.append(case)
        print(f"Question {i}/{len(chosen)} complete", flush=True)
    write(output / "predictions.json", rows)
    write(output / "human-review.json", packet)

    now = date(2025, 1, 2)
    for i, (q, passages, expected) in enumerate(spec["reader"], 1):
        facts = tuple(Fact(f"author-{n}", "fixture", "source excerpt", value, Source(now, str(n)), now)
                      for n, value in enumerate(passages))
        row = {"fixture": i, "answerable": expected is not None}
        try:
            result = tasks.answer_from_facts(q, facts, as_of=now)
            row["abstained"] = result.text is None
            row["passed"] = ((result.text is None) if expected is None else
                             expected.casefold() in (result.text or "").casefold())
            row["error"] = None
        except ProviderError as exc:
            row.update(passed=False, abstained=False, error=str(exc))
        validation.append(row)
    judges = {}
    for model in (QWEN, LLAMA):
        provider = ChatProvider(ProviderConfig("ollama", model, 50, **SETTINGS),
                                output / ("judge-fixture-qwen.sqlite" if model == QWEN else "judge-fixture-llama.sqlite"))
        counts = Counter()
        for answer, check, expected in spec["judge"]:
            try:
                result = judge(provider, answer, check)
            except ProviderError:
                result = "error"
            counts[f"{expected}->{result}"] += 1
        judges[model] = {"counts": dict(counts), "provider": provider.stats()}
    report = {"reader": validation, "judges": judges, "reader_provider": backend.stats(),
              "probe_provider": probe_backend.stats(), "wall_seconds": time.perf_counter() - started,
              "reconstructed_terminal_count": len(terminal)}
    write(output / "diagnostics.json", report)
    return report


if __name__ == "__main__":
    p = ArgumentParser(description=__doc__)
    for name in ("source", "prior", "output", "nli", "outcomes"):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    print(json.dumps(run(a.source, a.prior, a.output, a.nli, a.outcomes), sort_keys=True))
