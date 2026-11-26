"""Blind LongMemEval retrieval and frozen controller replay."""

from argparse import ArgumentParser
from collections import Counter
from datetime import date
from functools import lru_cache
import json
from math import log
from pathlib import Path
import re
import sqlite3
import time

from scripts.compare_local_verifiers import MODE, QWEN, SETTINGS, checksum, local_json
from scripts.longmemeval_inputs import DESIGN, events
from scripts.run_memora import ARTIFACTS, ROOT, sha, write
from scripts.replay_memora_full import make_adaptive, TerminalResponseMemo
from scripts.run_t2_development import frozen_rows
from scripts.updateset_v2_pilot import PROMPT_SCHEMA, QWEN_DIGEST
from trace_mem.adaptive_verification import AdaptiveAllocation, neutralized_score
from trace_mem.baselines import PreparedClaim, _eligible_target
from trace_mem.claims import Claim
from trace_mem.evidence_index_v2 import EvidenceIndexV2, Field
from trace_mem.features_v3 import CachedMiniLM, V3Features, pinned_nli
from trace_mem.llm_tasks import DIRECT_V2_PROMPT, LLMTasks, RESPONSE_SCHEMAS
from trace_mem.memora_benchmark import Question, _advance, run_suite
from trace_mem.memory import Fact, Source, TemporalMemory
from trace_mem.providers import ChatProvider, LimitExceeded, ProviderConfig, ProviderError
from trace_mem.reader_v2 import BUDGETS, read
from trace_mem.retrieval_diagnostic import trim
from trace_mem.semantic import _cosine, _unit_embeddings
from trace_mem.training import load_model

ENTITY = "longmemeval-history"
RESTRICT = re.compile(r"\b(?:forget|delete|erase|remove|discard)\b.{0,70}\b(?:memory|remember|record|info|detail|fact|note|what I|I said|my|everything|all)\b|\b(?:do not|don't|never)\s+(?:remember|store|retain|save|bring up|mention)\b", re.I)


def bm25(query, facts):
    keys = Counter(re.findall(r"\w+", query.casefold()))
    counts = [Counter(re.findall(r"\w+", f.value.casefold())) for f in facts]
    sizes = [sum(row.values()) for row in counts]
    avg = sum(sizes) / max(1, len(sizes)) or 1
    idf = {key: log(1 + (len(counts) - n + 0.5) / (n + 0.5))
           for key in keys for n in [sum(key in row for row in counts)]}
    def score(index):
        row, size = counts[index], sizes[index]
        return sum(idf[k] * row[k] * 2.2 / (row[k] + 1.2 * (0.25 + 0.75 * size / avg))
                   for k in keys if row[k])
    return [facts[i] for i in sorted(range(len(facts)), key=lambda i: (-score(i), i))]


def semantic(query, facts, embed):
    if not facts:
        return []
    q, *vectors = _unit_embeddings(embed, (query, *(f.value for f in facts)))
    return [facts[i] for i in sorted(range(len(facts)), key=lambda i: (-_cosine(q, vectors[i]), i))]


def transcript(events_):
    return [Fact(f"{event.session_id}/{event.turn}", ENTITY, event.role, event.message,
                 Source(event.observed_on, f"{event.session_id}/{event.turn}"), event.observed_on)
            for event in events_ if event.message.strip()]


def run_reader(case, facts, config, provider):
    started = time.perf_counter()
    q = Question(case["case"], "diagnostic", case["question"], date.fromisoformat(case["day"]))
    context = trim(q, facts, config["context_bytes"], config["top_k"])
    try:
        answer = read(provider, q.text, context, as_of=q.as_of, mode=config["reader_profile"]).answer
        status = "abstained" if answer.text is None else "answered"
    except LimitExceeded as error:
        if str(error) != "Input exceeds conservative preflight ceiling":
            raise
        answer = None
        status = "invalid"
    except ProviderError:
        answer = None
        status = "invalid"
    return {"status": status, "text": answer.text if answer else None,
            "retrieved": [x.source.reference for x in context],
            "latency_seconds": time.perf_counter() - started}


def prepared_claims(turns, checkpoint):
    by_source = {f"{e.session_id}/{e.turn}": e for e in turns}
    output = []
    for row in checkpoint:
        e = by_source[row["source"]]
        source = Source(e.observed_on, row["source"])
        for n, claim in enumerate(row["claims"]):
            fields = claim | {"effective_on": date.fromisoformat(claim["effective_on"]),
                              "expires_on": date.fromisoformat(claim["expires_on"]) if claim["expires_on"] else None}
            output.append(PreparedClaim(Claim(**fields), source, f"{row['source']}/{n}"))
    return output


def managed_fields(memory, turns, cutoff):
    sources = {f"{e.session_id}/{e.turn}": e.message for e in turns if e.role == "user"}
    fields = []
    facts = memory.retrieve(ENTITY, None, as_of=cutoff)
    for fact in facts:
        original = sources.get(fact.source.reference, "")
        if fact.source.observed_on <= cutoff and fact.value.casefold() in original.casefold():
            fields.append(Field(fact.fact_id, fact.source.reference, fact.value, fact.predicate,
                                fact.source.observed_on, fact.valid_from, fact.valid_to))
    return fields, len(facts) - len(fields)


def audit_prefix(claims, turns):
    memory = TemporalMemory()
    counts = Counter()
    for item in claims:
        counts["eligible"] += _eligible_target(memory, ENTITY, item.claim) is not None
        if item.claim.intent == "delete":
            counts["deletion_claims"] += 1
            counts["unresolved_deletions"] += not memory.matching_ids(
                ENTITY, item.claim.predicate, item.claim.value)
        _advance(memory, ENTITY, item)
    counts["source_restriction_signals"] = sum(
        e.role == "user" and RESTRICT.search(e.message) is not None for e in turns)
    return dict(counts)


class Meter:
    def __init__(self, provider):
        self.memo = TerminalResponseMemo(provider, provider.database.with_name("verify-terminal.sqlite"))
        self.provider = provider
        self.database = provider.database.with_name("verify-usage.sqlite")
        with sqlite3.connect(self.database) as db:
            db.execute("CREATE TABLE IF NOT EXISTS usage (key TEXT PRIMARY KEY, input INT, output INT)")
            self.usage = {k: (i, o) for k, i, o in db.execute("SELECT * FROM usage")}
        self.transport = provider.transport
        provider.transport = self.capture_usage
        self.last = None
        self.fatal = None

    def capture_usage(self, url, headers, body, timeout):
        raw = self.transport(url, headers, body, timeout)
        usage = raw.get("prompt_eval_count"), raw.get("eval_count")
        if all(type(n) is int and n >= 0 for n in usage):
            with sqlite3.connect(self.database) as db:
                db.execute("INSERT OR REPLACE INTO usage VALUES (?,?,?)", (self.last, *usage))
            self.usage[self.last] = usage
        return raw

    def generate(self, task, prompt, payload, validate):
        url, _, body = self.provider.request_for(self.provider.config, task, prompt, payload)
        key = self.provider.cache_key(task, url, body)
        self.last = key
        try:
            return self.memo.generate(task, prompt, payload, validate)
        except LimitExceeded as error:
            if str(error) != "Input exceeds conservative preflight ceiling":
                self.fatal = error
            raise


def reader_provider(root, config, name):
    return ChatProvider(ProviderConfig("ollama", QWEN, config["reader_limit"],
                        **(SETTINGS | {"max_output_tokens": BUDGETS[config["reader_profile"]]})),
                        root / f"{name}.sqlite")


def blind(root, nli, outcomes, *, retrieval_only=False):
    import torch

    if (ROOT / "results").resolve() not in root.resolve().parents:
        raise ValueError("Use ignored local results")
    config = json.loads(DESIGN.read_bytes())
    if {r["name"]: r["digest"] for r in local_json("/api/tags")["models"]}.get(QWEN) != QWEN_DIGEST:
        raise ValueError("Pinned local model unavailable")
    inputs = root / "inputs.json"
    manifest = {"inputs": sha(inputs), "design": sha(DESIGN), "qwen": QWEN_DIGEST,
                "settings": SETTINGS, "outcomes": sha(outcomes)}
    lock = root / "blind-freeze.json"
    if lock.exists() and json.loads(lock.read_bytes()) != manifest:
        raise ValueError("Blind prediction manifest changed")
    write(lock, manifest)
    torch.set_num_threads(4)
    encoder = CachedMiniLM()
    def embed(texts):
        return [v for i in range(0, len(texts), 24) for v in encoder(texts[i:i + 24])]
    reader = reader_provider(root, config, "blind-reader")
    reader_memo = TerminalResponseMemo(reader, root / "blind-reader-terminal.sqlite")
    transcript_rows = []
    directory = root / "blind"
    directory.mkdir(exist_ok=True)
    cases = json.loads(inputs.read_bytes())
    for case in cases:
        path = directory / f"{case['case']}-retrieval.json"
        if path.exists():
            row = json.loads(path.read_bytes())
        else:
            turns = transcript(events(case))
            q = case["question"]
            row = {name: run_reader(case, rank, config, reader_memo) for name, rank in
                   (("BM25", bm25(q, turns)), ("MiniLM", semantic(q, turns, embed)))}
            write(path, row)
        transcript_rows.append({"case": case["case"], "predictions": row})
        print(case["case"], "transcript diagnostics ready", flush=True)
    if retrieval_only:
        return
    extraction_freeze = json.loads((root / "extraction-freeze.json").read_bytes())
    if any(extraction_freeze[k] != manifest[k] for k in ("design", "inputs", "settings")):
        raise ValueError("Extraction and blind prediction inputs diverged")
    if checksum([DIRECT_V2_PROMPT, RESPONSE_SCHEMAS["verify-direct-v2"]]) != PROMPT_SCHEMA:
        raise ValueError("Frozen verifier prompt or schema changed")
    extraction = json.loads((root / "extraction-report.json").read_bytes())
    by_case = {r["case"]: r for r in extraction["cases"]}
    artifacts = json.loads((ARTIFACTS / "fit-freeze.json").read_bytes())["artifacts_sha256"]
    if any(sha(ARTIFACTS / name) != value for name, value in artifacts.items()):
        raise ValueError("Frozen controller artifacts changed")
    models = {m: load_model(ARTIFACTS / f) for m, f in (
        ("T1", "full.json"), ("T1-no-NLI", "no_nli.json"))}
    full = V3Features(lru_cache(maxsize=4096)(embed), lru_cache(maxsize=4096)(pinned_nli(nli)))
    reduced = V3Features(full.embed)
    builders = {"T1": full, "T1-no-NLI": reduced, "T2": full, "T2-no-NLI": reduced, "H-paced": reduced}
    train = frozen_rows(outcomes)["train"]
    adaptive = make_adaptive(config["planning_horizon"], train, models["T1"])
    def reduced_score(row):
        return neutralized_score(models["T1-no-NLI"], (row[0], 0.0, *row[2:]))
    adaptive["T2-no-NLI"] = AdaptiveAllocation(reduced_score, tuple(sorted(map(reduced_score, train))),
                                              config["planning_horizon"])
    verify_provider = ChatProvider(ProviderConfig("ollama", QWEN, config["verifier_limit"], **SETTINGS),
                                  root / "verify.sqlite")
    meter = Meter(verify_provider)
    tasks = LLMTasks(meter, verification_mode=MODE)

    for case, row in zip(cases, transcript_rows, strict=True):
        key = case["case"]
        path = directory / f"{key}-managed.json"
        if path.exists():
            row.update(json.loads(path.read_bytes()))
            continue
        data = {}
        turns = events(case)
        extract_path = root / "extraction" / f"{key}.json"
        checkpoint = json.loads(extract_path.read_bytes()) if extract_path.exists() else []
        claims = prepared_claims(turns, checkpoint)
        audit = audit_prefix(claims, turns)
        audit["extraction_errors"] = dict(Counter(r["error"] for r in checkpoint if "error" in r))
        quarantine = (audit["source_restriction_signals"] or audit.get("unresolved_deletions", 0)
                      or audit.get("deletion_claims", 0))
        cutoff = date.fromisoformat(case["day"])
        if by_case[key]["complete"] and not quarantine:
            for cap in config["caps"]:
                use = Counter()
                def observe(method, item, target, verdict, applied, failed):
                    if meter.last:
                        use[method, meter.last] += 1
                outcomes = run_suite(turns, claims, tasks, entity=ENTITY, models=models, builders=builders,
                                     mode="closed-loop", cap=cap, seed=config["seed"], adaptive=adaptive,
                                     methods=config["methods"], observer=observe)
                if meter.fatal:
                    raise meter.fatal
                for method, (memory, stats) in outcomes.items():
                    fields, rejected = managed_fields(memory, turns, cutoff)
                    index = EvidenceIndexV2(fields, "public-research-source-projection")
                    handle = index.retrieve(case["question"], cutoff, embed, k=config["top_k"])
                    prediction = run_reader(case, index.materialize(handle, ENTITY), config, reader_memo)
                    counts = {k: v for (m, k), v in use.items() if m == method}
                    data[f"{method}-{cap}"] = prediction | stats | {
                        "authorization_rejections": rejected, "authorized_fields": len(fields),
                        "logical_input_tokens": sum(n * meter.usage[k][0] for k, n in counts.items()
                                                    if k in meter.usage),
                        "logical_output_tokens": sum(n * meter.usage[k][1] for k, n in counts.items()
                                                     if k in meter.usage),
                        "logical_unmetered_calls": sum(n for k, n in counts.items() if k not in meter.usage)}
        status = "incomplete" if not by_case[key]["complete"] else "quarantined" if quarantine else "completed"
        update = {"managed": data, "managed_status": status, "audit": audit}
        row.update(update)
        write(path, update)
    report = {"cases": transcript_rows, "extraction": extraction, "reader": reader.stats(),
              "verifier": verify_provider.stats(), "manifest": manifest}
    write(root / "blind-predictions.json", report)
    write(root / "prediction-lock.json", {"sha256": sha(root / "blind-predictions.json")})


if __name__ == "__main__":
    p = ArgumentParser(description=__doc__)
    for arg in ("output", "nli", "outcomes"):
        p.add_argument(arg, type=Path)
    p.add_argument("--retrieval-only", action="store_true")
    args = p.parse_args()
    blind(args.output, args.nli, args.outcomes, retrieval_only=args.retrieval_only)
