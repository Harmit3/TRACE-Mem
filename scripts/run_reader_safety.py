"""Frozen reader comparison and fail-closed evidence-index evaluation."""

from argparse import ArgumentParser
from collections import Counter
from datetime import date
from functools import lru_cache
import json
from pathlib import Path
import time

from scripts.compare_local_verifiers import QWEN, SETTINGS, local_json
from scripts.extract_memora_full import seed_cache
from scripts.replay_memora_full import ENTITY, TerminalResponseMemo, inspect_claims, recover_extraction
from scripts.run_memora import ROOT, sha, write
from scripts.run_memora_failure_isolation import DESIGN as STEP25, PRIOR
from scripts.updateset_v2_pilot import QWEN_DIGEST
from trace_mem.evidence_index_v1 import EvidenceIndexV1, EvidenceRecord
from trace_mem.features_v3 import CachedMiniLM, MINILM_REVISION
from trace_mem.llm_tasks import LLMTasks
from trace_mem.memory import Fact, Source
from trace_mem.memora_benchmark import run_suite
from trace_mem.providers import ChatProvider, LimitExceeded, ProviderConfig, ProviderError
from trace_mem.reader_v2 import BUDGETS, ReaderResult, arithmetic, profile, read
from trace_mem.retrieval_diagnostic import candidate_event, evidence_metrics, in_scope, ranked_sources, trim
from trace_mem.semantic import retrieve_semantic


DESIGN = ROOT / "docs/memora_step26_freeze.json"
MODES = ("structured-b2", "transcript-diagnostic", "evidence-index-v1", "source-oracle-diagnostic")


def safety(queries, embed):
    """Validate live ACLs across a synthetic index and its alternate evidence channel."""
    day, revision, end = (date(2025, 1, d) for d in (1, 3, 6))
    index = EvidenceIndexV1()
    index.add(EvidenceRecord("base", "The prior home was Cedar Court.", "s1", day, day, "address"))
    index.add(EvidenceRecord("paraphrase", "The earlier address was Cedar Court.", "s2", day, day,
                             "archive", parents=("base",)))
    index.add(EvidenceRecord("current", "The home is Iris Road now.", "s3", revision, day.replace(day=2),
                             "address", supersedes="base"))
    index.add(EvidenceRecord("safe", "The current job is Granite Press.", "s4", day, day, "job"))
    index.add(EvidenceRecord("future", "A later job begins next month.", "s5", end, end, "job"))
    assertions = {}

    def ids(query, cutoff, subset=None):
        return set(index.retrieve(query, cutoff, embed, k=8, identifiers=subset).identifiers)

    assertions["historical_visible_before_revocation"] = "base" in ids(queries[0], day)
    assertions["backdated_change_not_visible_before_observation"] = "base" in ids(queries[0], day.replace(day=2))
    now = ids(queries[0], revision)
    assertions["current_supersession"] = "current" in now and "base" not in now
    assertions["future_excluded"] = "future" not in now
    handle = index.retrieve(queries[0], day, embed, k=8)
    prior_ids = {f.fact_id for f in index.materialize(handle, ENTITY)}
    index.revoke(source="s1")
    assertions["stale_handle_invalidated"] = not index.materialize(handle, ENTITY)
    assertions["historical_and_paraphrased_query_blocked"] = all(
        not ids(query, day) & {"base", "paraphrase"} for query in queries)
    assertions["alternate_index_blocked"] = not ids(queries[-1], day, ("paraphrase",))
    after = index.retrieve("work", revision, embed, k=8)
    assertions["unrelated_fact_and_cache_epoch"] = (
        "safe" in after.identifiers and not prior_ids & {f.fact_id for f in index.materialize(after, ENTITY)})
    index.revoke(scope="address")
    assertions["scope_revokes_current_replacement"] = "current" not in ids(queries[1], revision)
    index.revoke()
    assertions["unknown_scope_quarantines_every_channel"] = all(
        not ids(query, cutoff, subset) for query in queries for cutoff in (day, end)
        for subset in (None, ("safe", "paraphrase", "current")))
    return assertions


def measure_reader(question, facts, engine, provider, revised, *, as_of):
    try:
        result = (read(provider, question, facts, as_of=as_of, mode=engine) if revised
                  else ReaderResult(LLMTasks(provider).answer_from_facts(question, facts, as_of=as_of)))
        answer = result.answer
        ids = {f.fact_id for f in facts}
        citations_valid = (bool(answer.citations) and all(i in ids for i in answer.citations)
                           if answer.text is not None else not answer.citations)
        return {"answer": answer.text, "citations": answer.citations, "error": None,
                "citation_contract_valid": citations_valid,
                "canonicalized": result.canonicalized_abstention, "arithmetic": result.arithmetic}
    except LimitExceeded:
        raise
    except ProviderError as exc:
        return {"answer": None, "citations": (), "error": str(exc), "citation_contract_valid": False,
                "canonicalized": False, "arithmetic": False}


def literal_matches(answer, expected):
    return (answer is None if expected is None
            else answer is not None and all(key.casefold() in answer.casefold() for key in expected.split("|")))


def validate_reader(spec, providers):
    outcomes = []
    day = date(2025, 2, 5)
    for i, (question, mode, texts, expected) in enumerate(spec["reader"], 1):
        facts = tuple(Fact(f"f-{i}-{j}", "fixture", "source excerpt", text,
                           Source(day, str(j)), day) for j, text in enumerate(texts))
        for version in ("original", "v2"):
            selected = measure_reader(question, facts, mode, providers[version, mode],
                                      version == "v2", as_of=day)
            outcomes.append({"id": i, "reader": version, "profile": mode,
                             "answerable": expected is not None, "invalid": bool(selected["error"]),
                             "abstained": selected["answer"] is None and not selected["error"],
                             "passed": selected["error"] is None and literal_matches(selected["answer"], expected),
                             "citation_contract_valid": selected["citation_contract_valid"],
                             "arithmetic": selected["arithmetic"], "canonicalized": selected["canonicalized"],
                             "unexpected_answer": (expected is None and selected["answer"] is not None),
                             "nonempty": selected["answer"] is not None})
    return outcomes


def benchmark_index(events, state, audit, spec, cutoff):
    index = EvidenceIndexV1()
    source_ids = {}
    for event in events:
        if not in_scope(event, cutoff, spec):
            continue
        identifier = f"{event.session_id}/{event.turn}"
        source_ids[identifier] = "source/" + identifier
        index.add(EvidenceRecord(source_ids[identifier], event.message, identifier,
                                 event.observed_on, event.observed_on, "source excerpt"))
    structured = {}
    # Preserve observed histories and replacement lineage up to this cutoff.
    days = {cutoff, *(record.observed_on for record in index.records.values())}
    structured_facts = {f.fact_id: f for day in days for f in state.retrieve(ENTITY, None, as_of=day)}
    for fact_id, fact in sorted(structured_facts.items(), key=lambda p: (p[1].valid_from, p[0])):
        src = fact.source.reference
        if src not in source_ids:
            continue
        key = "structured/" + fact_id
        parent = source_ids[src]
        prior = structured.get(fact.supersedes)
        index.add(EvidenceRecord(key, fact.value, src, fact.source.observed_on, fact.valid_from,
                                 fact.predicate, (parent,), prior))
        structured[fact_id] = key
    # Step 24 unresolved deletions have unknown overlap with retained text and summaries.
    # Do not approximate authorization from text similarity.
    if audit["counts"].get("unresolved_delete"):
        index.revoke()
    return index


def run(source, prior, step25, output):
    import torch

    if (ROOT / "results").resolve() not in output.resolve().parents or sha(
            prior / "predictions.json") != PRIOR:
        raise ValueError("Use the pinned Step 24 input and an ignored output directory")
    spec = json.loads(DESIGN.read_bytes())
    if spec["output_budgets"] != BUDGETS:
        raise ValueError("Reader token profile disagrees with protocol")
    prior_spec = json.loads(STEP25.read_bytes())
    extraction = json.loads((prior / "extraction-report.json").read_bytes())
    _, pin, events, prepared, chosen, hashes = recover_extraction(source, prior, extraction)
    if {m["name"]: m["digest"] for m in local_json("/api/tags")["models"]}.get(QWEN) != QWEN_DIGEST:
        raise ValueError("Pinned local Qwen is unavailable")
    output.mkdir(parents=True, exist_ok=True)
    freeze = {"design_sha256": sha(DESIGN), "prior_design_sha256": sha(STEP25), "prior_predictions": PRIOR,
              "code": {str(p.relative_to(ROOT)): sha(p) for p in (
                  Path(__file__).resolve(), ROOT / "trace_mem/reader_v2.py",
                  ROOT / "trace_mem/evidence_index_v1.py", ROOT / "trace_mem/llm_tasks.py")},
              "session_hashes": hashes, "memora_revision": pin, "qwen": QWEN_DIGEST,
              "minilm": MINILM_REVISION, "settings": SETTINGS}
    manifest = output / "freeze.json"
    if manifest.exists() and json.loads(manifest.read_bytes()) != freeze:
        raise ValueError("Reader diagnostic configuration changed")
    write(manifest, freeze)
    started = time.perf_counter()
    torch.set_num_threads(4)
    encoder = CachedMiniLM()

    @lru_cache(maxsize=8192)
    def one(text):
        return tuple(encoder((text,))[0])

    def embed(values):
        return [one(v) for v in values]

    originals = ChatProvider(ProviderConfig("ollama", QWEN, 180, **SETTINGS), output / "original.sqlite")
    seed_cache(originals.database, step25 / "reader.sqlite")
    revised_backends = {mode: ChatProvider(ProviderConfig(
        "ollama", QWEN, 180, **(SETTINGS | {"max_output_tokens": tokens})), output / f"v2-{mode}.sqlite")
        for mode, tokens in BUDGETS.items()}
    providers = {("original", mode): TerminalResponseMemo(originals, output / "original-terminal.sqlite")
                 for mode in BUDGETS}
    providers.update({("v2", mode): TerminalResponseMemo(backend, output / f"terminal-{mode}.sqlite")
                      for mode, backend in revised_backends.items()})
    checks = safety(spec["safety_queries"], embed)
    write(output / "safety.json", checks)
    validation = validate_reader(spec, providers)
    write(output / "validation.json", validation)
    cutoff, = {q.observed_on for q in chosen}
    events = tuple(e for e in events if e.observed_on <= cutoff)
    prepared = tuple(c for c in prepared if c.source.observed_on <= cutoff)
    audit = inspect_claims(prepared)
    state, _ = run_suite(events, prepared, LLMTasks(originals), entity=ENTITY,
                         models={}, builders={}, mode="closed-loop", cap=0, seed=7, methods=("B2",))["B2"]
    index = benchmark_index(events, state, audit, prior_spec, cutoff)
    events_by_id = {f"{e.session_id}/{e.turn}": e for e in events}
    emitted = {item.source.reference for item in prepared}
    rows = []
    for i, (question, case) in enumerate(zip(chosen, prior_spec["questions"], strict=True), 1):
        evidence = {
            "structured-b2": tuple(hit.fact for hit in retrieve_semantic(
                state, question.text, entity=ENTITY, as_of=question.as_of, k=spec["k"], embed=embed)),
            "transcript-diagnostic": ranked_sources(question, events, prior_spec, embed, ENTITY),
            "evidence-index-v1": index.materialize(index.retrieve(
                question.text, question.as_of, embed, k=spec["k"]), ENTITY),
            "source-oracle-diagnostic": tuple(candidate_event(events_by_id[ref], ENTITY)
                for ref in case["spans"] if in_scope(events_by_id[ref], question.as_of, prior_spec)),
        }
        active = {f.source.reference for f in state.retrieve(ENTITY, None, as_of=question.as_of)}
        mode = profile(question.text, question.task)
        for arm, facts in evidence.items():
            bounded = trim(question, facts, spec["evidence_bytes"], spec["k"])
            stats = evidence_metrics(case["spans"], emitted, active, bounded)
            for reader in ("original", "v2"):
                selected = measure_reader(question.text, bounded, mode, providers[reader, mode],
                                          reader == "v2", as_of=question.as_of)
                rows.append({"number": i, "question_id": question.identifier, "task": question.task,
                             "mode": arm, "reader": reader, "profile": mode, **stats,
                             "context_facts": len(bounded), **selected})
        print(f"Question {i}/{len(chosen)} complete", flush=True)
    write(output / "predictions.json", rows)
    result = {"safety": checks, "index_quarantined": index.quarantined,
              "unresolved_delete_count": audit["counts"].get("unresolved_delete", 0),
              "records_indexed_before_policy": len(index.records),
              "validation": validation, "provider_original": originals.stats(),
              "provider_v2": {mode: provider.stats() for mode, provider in revised_backends.items()},
              "wall_seconds": time.perf_counter() - started}
    write(output / "diagnostic.json", result)
    return result


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    for name in ("source", "previous", "step25", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.source, args.previous, args.step25, args.output), sort_keys=True))
