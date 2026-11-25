"""Frozen local deletion-resolution validation and human review export."""

from argparse import ArgumentParser
from collections import Counter
from dataclasses import asdict
from datetime import date
import json
from pathlib import Path
import time

from scripts.compare_local_verifiers import QWEN, SETTINGS, local_json
from scripts.replay_memora_full import ENTITY, recover_extraction
from scripts.run_memora import ROOT, sha, write
from scripts.run_memora_failure_isolation import PRIOR
from scripts.run_reader_safety import safety
from scripts.updateset_v2_pilot import QWEN_DIGEST
from trace_mem.authorized_answer_cache import AuthorizedAnswerCache
from trace_mem.baselines import _apply
from trace_mem.deletion_resolver_v1 import Candidate, Proposal, REMOVE, exact_baseline, propose
from trace_mem.evidence_index_v1 import EvidenceIndexV1, EvidenceRecord
from trace_mem.features_v3 import CachedMiniLM, MINILM_REVISION
from trace_mem.llm_tasks import Answer
from trace_mem.memory import TemporalMemory
from trace_mem.providers import ChatProvider, LimitExceeded, ProviderConfig, ProviderError


DESIGN = ROOT / "docs/memora_step27_freeze.json"
OPTIONS = (
    "Approve only listed source/field targets for restriction; keep unresolved derivatives blocked.",
    "Revise the proposed targets or scope; leave the request quarantined until verified.",
    "Classify as correction or temporary restriction and specify the applicability interval.",
    "Classify as a false deletion claim and name the sources explicitly authorized for release.",
    "Keep pending and release nothing.",
)


def candidates_at_request(events, items):
    """Reconstruct the old exact baseline and causal source candidate stream."""
    previous = []
    cursor = 0
    memory = TemporalMemory()
    order = lambda e: (e.observed_on, e.session_id, e.turn)
    index = {f"{e.session_id}/{e.turn}": e for e in events if e.role == "user"}
    dates = set()
    for item in items:
        source = index[item.source.reference]
        while cursor < len(events) and order(events[cursor]) < order(source):
            prior = events[cursor]
            if prior.role == "user":
                previous.append(prior)
            cursor += 1
        claim = item.claim
        same = memory.matching_ids(ENTITY, claim.predicate, claim.value)
        if claim.intent == "delete" and not same:
            facts = {f.source.reference: f for day in dates | {source.observed_on}
                     for f in memory.retrieve(ENTITY, None, as_of=day)}
            context = [e.message for e in previous if e.session_id == source.session_id][-2:]
            eligible = []
            for e in previous:
                if REMOVE.search(e.message):
                    continue
                key = f"{e.session_id}/{e.turn}"
                fact = facts.get(key)
                eligible.append(Candidate(key, fact.predicate if fact else "source excerpt",
                                          fact.value if fact else "", e.message, e.observed_on))
            yield source, item, context, tuple(eligible)
        _apply(memory, ENTITY, claim, item.source, item.fact_id, "B2", None, None, None)
        dates.add(claim.effective_on)


def score(rows, key):
    matched = proposed = expected = false_requests = unresolved = 0
    retained = total = 0
    for row in rows:
        actual, truth = set(row[key]), set(row["gold"])
        matched += len(actual & truth)
        proposed += len(actual)
        expected += len(truth)
        false_requests += bool(actual - truth)
        unresolved += bool(truth - actual)
        total += row["pool_size"]
        retained += row["pool_size"] - len(actual)
    return {"matched": matched, "proposed": proposed, "expected": expected,
            "precision": matched / proposed if proposed else None,
            "recall": matched / expected if expected else None,
            "false_targets": proposed - matched, "false_request_rate": false_requests / len(rows),
            "unresolved_targeted_requests": unresolved,
            "hypothetical_retained_if_proposals_applied": retained, "candidate_records": total}


def evaluate_fixtures(design, provider, embed):
    cutoff = date.fromisoformat(design["cutoff"])
    rows = []
    for name, text, context, predicate, value, scope, category, gold, records in design["fixtures"]:
        candidates = tuple(Candidate(i, p, v, t, date.fromisoformat(day), tuple(aliases), s)
                           for i, p, v, t, day, aliases, s in records)
        try:
            result = propose(provider, embed, text, context, value, candidates, cutoff, scope=scope,
                             k=design["k"])
            error = None
        except LimitExceeded:
            raise
        except ProviderError as exc:
            result = Proposal("unresolved", "none", (), ())
            error = str(exc)
        rows.append({"id": name, "gold": gold, "gold_intent": category, "semantic": result.targets,
                     "semantic_intent": result.intent, "relation": result.relation,
                     "exact": exact_baseline(predicate, value, candidates, cutoff),
                     "pool_size": sum(c.observed_on <= cutoff for c in candidates), "error": error})
    return rows


def answer_cache_checks():
    day = date(2025, 2, 1)
    index = EvidenceIndexV1()
    index.add(EvidenceRecord("home", "A private address.", "source", day, day, "address"))
    index.add(EvidenceRecord("derived", "A paraphrase of the private address.", "other",
                             day, day, "summary", parents=("home",)))
    embed = lambda inputs: [[1.0] for _ in inputs]
    handle = index.retrieve("prior residence", day, embed, k=2, identifiers=["derived"])
    fact, = index.materialize(handle, "fixture")
    cache = AuthorizedAnswerCache(index, "fixture")
    cache.store("request", handle, Answer(fact.value, (fact.fact_id,)))
    before = cache.fetch("request") is not None
    index.revoke(source="source")
    return {"cached_answer_allowed_before_restriction": before,
            "cached_answer_blocked_after_restriction": cache.fetch("request") is None,
            "derived_handle_blocked_after_restriction": not index.materialize(handle, "fixture")}


def packet_markdown(rows):
    output = ["# Step 27 deletion scope review", "", "All 18 requests require review.",
              "A reviewer should record a decision, approved source IDs, allowed or denied text ranges,",
              "scope, and whether any derivative can be safely retained. Default: pending and blocked.", ""]
    for i, row in enumerate(rows, 1):
        output += [f"## {i}. Source {row['reference']} ({row['date']})", "", row["request"], "",
                   f"Analyst classification: {row['analyst_intent']}. {row['note']}",
                   f"Resolver proposal: {row['resolver']['intent']} / {row['resolver']['relation']}.",
                   f"Chosen target IDs: {', '.join(row['resolver']['targets']) or 'none'}.",
                   "Review decision, fields, and approved source scopes: ___", ""]
        if row["context"]:
            output += ["Earlier same-session user context:", *[f"- {item}" for item in row["context"]], ""]
        output.extend(f"- Target {item['identifier']} ({item['role']}) · {item['text']}"
                      for item in row["candidates"])
        output += ["", *[f"- [ ] {option}" for option in OPTIONS], ""]
    return "\n".join(output) + "\n"


def run(repo, prior, output):
    import torch

    if (ROOT / "results").resolve() not in output.resolve().parents or sha(
            prior / "predictions.json") != PRIOR:
        raise ValueError("Use pinned Step 24 data with an ignored output directory")
    design = json.loads(DESIGN.read_bytes())
    _, revision, events, items, _, hashes = recover_extraction(
        repo, prior, json.loads((prior / "extraction-report.json").read_bytes()))
    real = list(candidates_at_request(events, items))
    if {item.source.reference for _, item, _, _ in real} != set(design["source_review"]):
        raise ValueError("The frozen source audit differs from the unresolved B2 ledger")
    if {m["name"]: m["digest"] for m in local_json("/api/tags")["models"]}.get(QWEN) != QWEN_DIGEST:
        raise ValueError("Pinned Qwen unavailable")
    output.mkdir(parents=True, exist_ok=False)
    freeze = {"design_sha256": sha(DESIGN), "source_revision": revision, "prior_predictions": PRIOR,
              "qwen": QWEN_DIGEST, "minilm": MINILM_REVISION, "settings": SETTINGS,
              "session_hashes": hashes}
    write(output / "freeze.json", freeze)
    started = time.perf_counter()
    torch.set_num_threads(4)
    model = CachedMiniLM()
    memo = {}

    def embed(texts):
        unseen = list(dict.fromkeys(text for text in texts if text not in memo))
        for i in range(0, len(unseen), 32):
            batch = unseen[i:i + 32]
            memo.update(zip(batch, model(batch), strict=True))
        return [memo[text] for text in texts]

    provider = ChatProvider(ProviderConfig("ollama", QWEN, 80, **SETTINGS), output / "resolver.sqlite")
    fixtures = evaluate_fixtures(design, provider, embed)
    source_index = {f"{e.session_id}/{e.turn}": e for e in events}
    audit, proposal_rows = [], []
    for event, item, context, candidates in real:
        reference = item.source.reference
        category, expected, note = design["source_review"][reference]
        try:
            result = propose(provider, embed, event.message, context, item.claim.value, candidates,
                             event.observed_on, k=design["k"])
            error = None
        except LimitExceeded:
            raise
        except ProviderError as exc:
            result = Proposal("unresolved", "none", (), ())
            error = str(exc)
        ranked = tuple(dict.fromkeys((*expected, *result.ranked[:3], *result.targets)))
        trace = [{"identifier": key, "text": source_index[key].message,
                  "date": source_index[key].observed_on.isoformat(),
                  "role": "source audit" if key in expected else "resolver rank"}
                 for key in ranked]
        audit.append({"reference": reference, "date": event.observed_on.isoformat(),
                      "request": event.message, "context": context,
                      "extracted": {"predicate": item.claim.predicate, "value": item.claim.value},
                      "analyst_intent": category, "note": note, "candidates": trace,
                      "resolver": asdict(result), "error": error,
                      "human_review": "pending", "approved_release": []})
        proposal_rows.append({"reference": reference, "analyst_intent": category,
                              "model_intent": result.intent, "relation": result.relation,
                              "analyst_target_overlap": bool(set(expected) & set(result.targets)),
                              "single_target_proposed": bool(result.targets),
                              "proposal_error": error is not None})
    write(output / "review.json", audit)
    (output / "review.md").write_text(packet_markdown(audit), encoding="utf-8", newline="\n")
    temporal = safety(["where", "previous residence", "home location", "archived address"], embed)
    temporal.update(answer_cache_checks())
    scores = {method: score(fixtures, method) for method in ("exact", "semantic")}
    metrics = scores["semantic"]
    gate = design["gate"]
    passes = (metrics["precision"] is not None and metrics["precision"] >= gate["precision_min"]
              and metrics["recall"] >= gate["recall_min"] and metrics["false_targets"] <= gate["max_false_targets"]
              and all(temporal.values()))
    result = {"freeze_sha256": sha(output / "freeze.json"), "fixtures": fixtures,
              "metrics": scores, "resolver_gate_passes": passes, "safety": temporal,
              "real": {"requests": len(real), "analyst_intents": dict(Counter(
                  row["analyst_intent"] for row in proposal_rows)),
                  "model_intents": dict(Counter(row["model_intent"] for row in proposal_rows)),
                  "proposal_rows": proposal_rows, "approvals": 0, "authorized_recovered_records": 0,
                  "quarantine_released": False},
              "provider": provider.stats(), "wall_seconds": time.perf_counter() - started}
    write(output / "report.json", result)
    return {key: result[key] for key in ("metrics", "resolver_gate_passes", "safety", "provider", "wall_seconds")}


if __name__ == "__main__":
    p = ArgumentParser(description=__doc__)
    for name in ("memora", "prior", "output"):
        p.add_argument(name, type=Path)
    args = p.parse_args()
    print(json.dumps(run(args.memora, args.prior, args.output), sort_keys=True))
