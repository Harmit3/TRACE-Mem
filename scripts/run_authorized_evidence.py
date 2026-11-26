"""Verify the local field allowlist and evaluate only after all safety gates pass."""

from argparse import ArgumentParser
from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
import time

from scripts.compare_local_verifiers import QWEN, SETTINGS, local_json
from scripts.extract_memora_full import DESIGN as FULL
from scripts.replay_memora_full import ENTITY, recover_extraction, TerminalResponseMemo
from scripts.run_memora import ROOT, sha, write
from scripts.run_memora_failure_isolation import DESIGN as STEP25, PRIOR
from scripts.updateset_v2_pilot import QWEN_DIGEST
from trace_mem.authorized_answer_cache import AuthorizedAnswerCache
from trace_mem.evidence_index_v2 import EvidenceIndexV2, Field
from trace_mem.features_v3 import CachedMiniLM, MINILM_REVISION
from trace_mem.llm_tasks import Answer
from trace_mem.providers import ChatProvider, LimitExceeded, ProviderConfig, ProviderError
from trace_mem.reader_v2 import BUDGETS, profile, read
from trace_mem.retrieval_diagnostic import trim


DESIGN = ROOT / "docs/memora_step29_protocol.json"


def checked_span(text, excerpt):
    if not excerpt or text.count(excerpt) != 1:
        raise ValueError("Expected one exact, unambiguous source span")
    start = text.index(excerpt)
    return start, start + len(excerpt)


def overlap(left, right):
    return max(left[0], right[0]) < min(left[1], right[1])


def fields_from_review(config, annotation, worksheet, grant_plan, events):
    if sha(annotation) != config["annotations_sha256"] or sha(grant_plan) != config["private_span_plan_sha256"]:
        raise ValueError("Unexpected annotation or frozen private span-plan hash")
    data = json.loads(annotation.read_text(encoding="utf-8-sig"))
    rows = json.loads(worksheet.read_bytes())
    decisions = data["decisions"]
    if (data["schema_version"] != 1 or data["evidence_released"] or sha(worksheet) != data["worksheet_sha256"]
            or len(decisions) != 18 or len(rows) != 18
            or Counter(d["annotation"] for d in decisions) != config["expected_cases"]):
        raise ValueError("Incomplete or inconsistent human annotation")
    def order(event):
        return event.observed_on, event.session_id, event.turn

    roots = {}
    superseded = {}
    correction_sources = set()
    requests = set()
    for n, (d, row) in enumerate(zip(decisions, rows, strict=True), 1):
        request = events[d["request_source"]]
        if (d["case_number"] != n or d["status"] != "human-reviewed" or d["approved_release"]
                or d["request_source"] != row["reference"] or request.message != row["request"]
                or request.observed_on.isoformat() != row["date"]):
            raise ValueError("Decision and focal source disagree")
        requests.add(row["reference"])
        mapped = {x["identifier"]: x for x in row["candidates"] if x["role"] == "source audit"}
        for key, candidate in mapped.items():
            event = events[key]
            if event.message != candidate["text"] or event.observed_on.isoformat() != candidate["date"] or order(event) >= order(request):
                raise ValueError("Invalid chronological source reference")
        if d["annotation"] == "targeted_forgetting":
            if d["option"] != 1 or set(d["restricted_sources"]) != set(mapped):
                raise ValueError("Target disagrees with the reviewed source scope")
            roots.update({(n, key): mapped[key]["text"] for key in d["restricted_sources"]})
        elif d["annotation"] == "preference_correction":
            if (d["option"] != 3 or d["current_source"] != row["reference"]
                    or d["effective_from"] != row["date"] or d["superseded_source"] not in mapped):
                raise ValueError("Invalid supersession")
            correction_sources.add(d["current_source"])
            history = d.get("preference_history", [])
            if history:
                for old, new in zip(history, history[1:]):
                    if (events[old["source"]].observed_on.isoformat() != old["date"] or
                            events[new["source"]].observed_on.isoformat() != new["date"] or
                            order(events[old["source"]]) >= order(events[new["source"]])):
                        raise ValueError("Preference timeline differs from source")
                    superseded[old["source"]] = new["date"]
            else:
                superseded[d["superseded_source"]] = d["effective_from"]
        elif d["option"] != 4 or d.get("restricted_sources"):
            raise ValueError("An extraction error cannot authorize a field or document")
    plan = json.loads(grant_plan.read_bytes())
    if (plan["schema"] != 1 or {(x["case"], x["source"]) for x in plan["deny"]} != set(roots)
            or len(plan["deny"]) != len(roots)):
        raise ValueError("The plan must cover every denied source for every case")
    denied = defaultdict(list)
    for item in plan["deny"]:
        key = item["case"], item["source"]
        denied[item["source"]].append(checked_span(roots[key], item["span"]))
    fields = []
    for item in plan["allow"]:
        source = item["source"]
        event = events[source]
        extent = checked_span(event.message, item["span"])
        if (any(overlap(extent, r) for r in denied[source])
                or source in requests - correction_sources
                or item["end"] != superseded.get(source)):
            raise ValueError("The positive grant overlaps a denied field or temporal policy")
        fields.append(Field(item["identity"], source, item["span"], item["predicate"],
                            event.observed_on, event.observed_on,
                            date.fromisoformat(item["end"]) if item["end"] else None))
    if not set(superseded).issubset({f.source for f in fields}):
        raise ValueError("Reviewed historical preference is missing")
    return tuple(fields), plan, requests, superseded, correction_sources


def safety(fields, plan, requests, superseded, correction_sources, fingerprint, cutoff):
    index = EvidenceIndexV2(fields, fingerprint)
    embedded = []

    def probe(texts):
        embedded.extend(texts[1:])
        return [[1.0, 0.0] for _ in texts]

    days = sorted({cutoff, *(f.observed for f in fields), *(date.fromisoformat(s) for s in superseded.values())})
    views = {}
    for day in days:
        handle = index.retrieve("earlier context or a related phrasing", day, probe, k=len(fields))
        views[day] = index.materialize(handle, ENTITY)
    visible = tuple(f for facts in views.values() for f in facts)
    per_case = defaultdict(list)
    for restriction in plan["deny"]:
        value = restriction["span"].strip().casefold()
        per_case[restriction["case"]].append(
            all(value not in f.value.casefold() for f in visible)
            and all(value not in text.casefold() for text in embedded))
    cases = {n: all(results) for n, results in per_case.items()}
    for n in (4, 16):
        cases[n] = (all(f.source.reference not in superseded for f in views[cutoff]) and
                    all(any(f.source.reference == key for f in visible) for key in superseded) and
                    all(any(f.source.reference == key for f in views[cutoff]) for key in correction_sources))
    for n in (5, 11):
        cases[n] = all(f.source.reference not in requests - correction_sources for f in visible)
    recovered_spans = {(f.source.reference, f.value) for f in visible}
    denied_sources = {x["source"] for x in plan["deny"]}
    old_handle = index.retrieve("work", cutoff, probe, k=1)
    facts = index.materialize(old_handle, ENTITY)
    cache = AuthorizedAnswerCache(index, ENTITY)
    cache.store("old", old_handle, Answer(facts[0].value, (facts[0].fact_id,)))
    old_cache_hit = cache.fetch("old") is not None
    index.rebuild(fields, fingerprint)
    stale_rejected = not index.materialize(old_handle, ENTITY) and cache.fetch("old") is None
    cross_view = index.retrieve("repeat the previous sensitive fact", cutoff, probe, k=100,
                                view=("ungranted", "unmanaged-copy"))
    bad_lineage = Field("bad", fields[0].source, "paraphrased unauthorized summary",
                        "derived", fields[0].observed, fields[0].start, parents=(fields[0].identity,))
    try:
        EvidenceIndexV2((fields[0], bad_lineage), fingerprint)
    except ValueError:
        rejects_unverified_derivative = True
    else:
        rejects_unverified_derivative = False
    return {"cases": dict(sorted(cases.items())), "checks": {
                "mixed_source_retention": all((f.source, f.text) in recovered_spans
                    for f in fields if f.source in denied_sources),
                "all_positive_grants_retained": len(recovered_spans)
                    == len(fields),
                "old_cache_invalidated": old_cache_hit and stale_rejected,
                "alternate_index_denies_ungranted": not cross_view.identities,
                "derivative_with_unverified_text_denied": rejects_unverified_derivative,
                "deletion_requests_not_indexed": all(f.source.reference not in requests - correction_sources
                    for f in visible),
            }, "retained_fields": len(recovered_spans), "current_fields": len(views[cutoff]),
            "verified_mixed_source_fields": sum(f.source in denied_sources for f in fields),
            "denied_span_links": len(plan["deny"]),
            "restricted_span_leaks": sum(not value for values in per_case.values() for value in values)}


def run(repository, prior, annotation, worksheet, grant_plan, output):
    import torch

    if (ROOT / "results").resolve() not in output.resolve().parents or sha(prior / "predictions.json") != PRIOR:
        raise ValueError("Requires a local ignored output and the pinned Step 24 input")
    config = json.loads(DESIGN.read_bytes())
    _, revision, events, prepared, questions, session_hashes = recover_extraction(
        repository, prior, json.loads((prior / "extraction-report.json").read_bytes()))
    user_events = {f"{e.session_id}/{e.turn}": e for e in events if e.role == "user"}
    fields, plan, requests, superseded, corrections = fields_from_review(
        config, annotation, worksheet, grant_plan, user_events)
    cutoff, = {q.observed_on for q in questions}
    output.mkdir(parents=True, exist_ok=False)
    freeze = {"protocol": sha(DESIGN), "annotation": sha(annotation), "plan": sha(grant_plan),
              "memora_revision": revision, "session_hashes": session_hashes,
              "qwen": QWEN_DIGEST, "minilm": MINILM_REVISION, "reader": "v2", "settings": SETTINGS}
    write(output / "freeze.json", freeze)
    audit = safety(fields, plan, requests, superseded, corrections, sha(grant_plan), cutoff)
    audit.update({"source_turns": len(user_events), "recovered_source_turns": len({f.source for f in fields}),
                  "unimported_old_structured_claims": len(prepared),
                  "false_deletions_among_positive_grants": len(fields) - audit["retained_fields"]})
    audit["passes"] = (set(audit["cases"]) == set(range(1, 19))
        and all(audit["cases"].values()) and all(audit["checks"].values())
        and audit["restricted_span_leaks"] == 0)
    write(output / "safety.json", audit)
    if not audit["passes"]:
        return {"safety": audit, "evaluated": False}
    if {x["name"]: x["digest"] for x in local_json("/api/tags")["models"]}.get(QWEN) != QWEN_DIGEST:
        raise ValueError("Pinned local Qwen unavailable")
    started = time.perf_counter()
    torch.set_num_threads(4)
    model = CachedMiniLM()
    vectors = {}
    def embed(texts):
        missing = list(dict.fromkeys(t for t in texts if t not in vectors))
        for i in range(0, len(missing), 32):
            batch = missing[i:i+32]
            vectors.update(zip(batch, model(batch), strict=True))
        return [vectors[t] for t in texts]
    index = EvidenceIndexV2(fields, sha(grant_plan))
    files = {mode: ChatProvider(ProviderConfig("ollama", QWEN, 40,
             **(SETTINGS | {"max_output_tokens": tokens})), output / f"reader-{mode}.sqlite")
             for mode, tokens in BUDGETS.items()}
    providers = {mode: TerminalResponseMemo(provider, output / f"terminal-{mode}.sqlite")
                 for mode, provider in files.items()}
    nominations = json.loads(STEP25.read_bytes())["questions"]
    predictions = []
    for number, (q, reference) in enumerate(zip(questions, nominations, strict=True), 1):
        handle = index.retrieve(q.text, q.as_of, embed, k=config["k"])
        candidates = trim(q, index.materialize(handle, ENTITY), config["evidence_bytes"], config["k"])
        mode = profile(q.text, q.task)
        error = None
        try:
            answer = read(providers[mode], q.text, candidates, as_of=q.as_of, mode=mode).answer
        except LimitExceeded:
            raise
        except ProviderError as exc:
            error = str(exc)
            answer = Answer(None, ())
        predictions.append({"number": number, "question_id": q.identifier, "task": q.task,
                            "mode": "authorized-evidence-v2", "reader": "v2",
                            "answer": answer.text, "error": error, "context_facts": len(candidates),
                            "nominated_source_turns": len(reference["spans"]),
                            "retrieved_turns": len(set(reference["spans"]) &
                                                   {f.source.reference for f in candidates})})
        print(f"Question {number}/{len(questions)} complete", flush=True)
    write(output / "predictions.json", predictions)
    result = {"safety": audit, "evaluated": True, "reader_stats": {k: p.stats() for k, p in files.items()},
              "wall_seconds": time.perf_counter() - started}
    write(output / "diagnostic.json", result)
    return result


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    for name in ("repository", "prior", "annotation", "worksheet", "grant_plan", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.repository, args.prior, args.annotation, args.worksheet,
                         args.grant_plan, args.output), sort_keys=True))
