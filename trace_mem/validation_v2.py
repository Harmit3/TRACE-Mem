"""Approval-gated synthetic evaluation, v2. No model backend is started here."""

from collections import Counter
from copy import deepcopy
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from statistics import fmean
import random
import sqlite3
from time import perf_counter

from trace_mem.baselines import PreparedClaim, _eligible_target
from trace_mem.adaptive_verification import AdaptiveAllocation, heuristic_score, neutralized_score
from trace_mem.causal_horizon_v1 import CalendarPlanner
from trace_mem.evidence_index_v2 import EvidenceIndexV2, Field
from trace_mem.llm_tasks import Answer
from trace_mem.memora_benchmark import _advance, _apply_verdict
from trace_mem.memory import TemporalMemory
from trace_mem.providers import ProviderError
from trace_mem.training import load_model
from trace_mem.verification import Budget, select_ranked


VERSION = "independent-validation-v2"
POLICIES = ("B3", "T2", "H-paced", "T2-no-NLI")
CAPS = (0, 2, 5)
BOOTSTRAP_SEED = 360091
BOOTSTRAP_DRAWS = 10000
VERDICTS = {"same", "update", "historical", "unrelated", "insufficient_evidence"}


@dataclass(frozen=True)
class Episode:
    identity: str
    family: str
    opening: date
    closing: date
    events: tuple[PreparedClaim, ...]
    permitted: frozenset[str]
    restricted_values: tuple[str, ...]
    support: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Check:
    observed: date
    effective: date
    predicate: str
    values: tuple[str, ...]
    type: str


@dataclass(frozen=True)
class Gold:
    checks: tuple[Check, ...]
    answerable: bool
    answers: tuple[str, ...]
    harmful: frozenset[str]


def signature(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                             default=lambda item: item.isoformat() if isinstance(item, date) else sorted(item)
                             ).encode()).hexdigest()


def validate(episode, gold):
    if not episode.identity or not episode.family or episode.closing < episode.opening:
        raise ValueError("Missing identities or invalid calendar")
    seen = set()
    previous = episode.opening
    for item in episode.events:
        source = item.source
        if (not previous <= source.observed_on <= episode.closing or not source.reference
                or not item.fact_id or item.fact_id in seen):
            raise ValueError("Events must have chronological dates and unique identities")
        seen.add(item.fact_id)
        previous = source.observed_on
    if not episode.permitted <= seen or any(not value.strip() for value in episode.restricted_values):
        raise ValueError("Invalid source authorization")
    if not gold.harmful <= seen or (
            Counter(c.type for c in gold.checks) != {"current": 6, "historical": 5}):
        raise ValueError("Gold must provide six current and five historical checks")
    if len({(c.observed, c.effective, c.predicate, c.type) for c in gold.checks}) != 11:
        raise ValueError("Duplicate gold checkpoint")
    for check in gold.checks:
        if (not episode.opening <= check.observed <= episode.closing
                or not episode.opening <= check.effective <= check.observed or not check.predicate
                or len(set(check.values)) != len(check.values)
                or any(not v.strip() for v in check.values)
                or (check.type == "current") != (check.observed == check.effective)):
            raise ValueError("Invalid gold time or values")
    if not any(c.type == "current" and c.observed == episode.closing for c in gold.checks):
        raise ValueError("Missing final-state check")
    if gold.answerable != bool(gold.answers) or any(not a.strip() for a in gold.answers):
        raise ValueError("Invalid reader gold")


def frozen_rules(full_path, reduced_path, digests, training_reference):
    """Bind the approved controller files to their historical deployment rules."""
    paths = (Path(full_path), Path(reduced_path))
    if tuple(sha256(p.read_bytes()).hexdigest() for p in paths) != tuple(digests):
        raise ValueError("Controller artifact differs from approved digest")
    full, reduced = map(load_model, paths)
    def score_full(vector):
        return neutralized_score(full, vector)
    def score_reduced(vector):
        return neutralized_score(reduced, (vector[0], 0.0, *vector[2:]))
    training_reference = tuple(training_reference)
    return {
        name: AdaptiveAllocation(fn, tuple(sorted(map(fn, training_reference))), 5)
        for name, fn in (("T2", score_full), ("H-paced", heuristic_score), ("T2-no-NLI", score_reduced))
    }


class ExactLedger:
    """Persistent request accounting. Only exact successful responses are reusable."""

    def __init__(self, database, provider_fingerprint):
        if not provider_fingerprint:
            raise ValueError("Pin the provider, prompt, schema and inference settings")
        self.database = database
        self.fingerprint = provider_fingerprint
        with closing(sqlite3.connect(database)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS outcomes (key TEXT PRIMARY KEY, verdict TEXT, input INT, output INT)")
            db.execute("CREATE TABLE IF NOT EXISTS spend (id INTEGER PRIMARY KEY, key TEXT, seconds REAL, valid INT)")

    def call(self, claim, target, evidence, provider):
        key = signature([VERSION, self.fingerprint, asdict(claim), asdict(target), evidence])
        with closing(sqlite3.connect(self.database)) as db, db:
            previous = db.execute("SELECT verdict,input,output FROM outcomes WHERE key=?", (key,)).fetchone()
            if previous:
                return *previous, False, 0.0
            # Persist an attempted dispatch before provider invocation.
            attempt = db.execute("INSERT INTO spend(key) VALUES (?)", (key,)).lastrowid
            db.commit()
            start = perf_counter()
            try:
                verdict, sent, received = provider(claim, target, evidence)
                valid = verdict in VERDICTS and all(type(x) is int and x >= 0 for x in (sent, received))
                if not valid:
                    verdict = "invalid"
                    sent = received = None
            except (ProviderError, TimeoutError, ValueError, TypeError):
                verdict, sent, received = "invalid", None, None
            duration = perf_counter() - start
            db.execute("UPDATE spend SET seconds=?,valid=? WHERE id=?",
                       (duration, int(verdict != "invalid"), attempt))
            if verdict != "invalid":
                db.execute("INSERT INTO outcomes VALUES (?,?,?,?)", (key, verdict, sent, received))
            return verdict, sent, received, True, duration


def allowed(episode, identity, value):
    return (identity in episode.permitted and all(r.casefold() not in value.casefold()
                                                  for r in episode.restricted_values))


def replay(episode, method, cap, mode, rules, feature, provider, ledger, *, stress=(1, 1)):
    """Operate on source-authorized input only. Gold is unavailable to this function."""
    if (method not in POLICIES or type(cap) is not int or cap not in CAPS
            or mode not in ("closed-loop", "fixed")):
        raise ValueError("Unknown experimental condition")
    memory, budget = TemporalMemory(), Budget(cap)
    calendar = CalendarPlanner(episode.opening, episode.closing, *stress)
    evidence = dict(episode.support)
    if mode == "fixed" and cap:
        frozen = TemporalMemory()
        pool = []
        for item in episode.events:
            target = _eligible_target(frozen, "subject", item.claim)
            if (target is not None and allowed(episode, target.fact_id, target.value)
                    and allowed(episode, item.fact_id, item.claim.value)):
                pool.append((item, target))
            _advance(frozen, "subject", item)
        ranks = (list(range(min(cap, len(pool)))) if method == "B3" else select_ranked(
            [rules[method].score(feature[method](item, t, 1.0)) for item, t in pool], min(cap, len(pool))))
        selected = {pool[i][0].fact_id: pool[i][1] for i in ranks}
    else:
        selected = {}
    metrics = Counter()
    visits = []
    decision_trace = []
    snapshots = {}
    quarantined = False
    for item in episode.events:
        claim, day = item.claim, item.source.observed_on
        unresolved = claim.intent == "delete" and not memory.matching_ids("subject", claim.predicate, claim.value)
        quarantined |= unresolved
        live = _eligible_target(memory, "subject", claim)
        eligible = (not quarantined and live is not None and allowed(episode, live.fact_id, live.value)
                    and allowed(episode, item.fact_id, claim.value))
        target = selected.get(item.fact_id) if mode == "fixed" else None
        forecast = rank = None
        if eligible:
            previous = metrics["opportunities"]
            forecast = calendar.future(day, previous)
            metrics["opportunities"] += 1
            if mode == "closed-loop" and budget.remaining:
                if method == "B3":
                    target = live
                else:
                    rule = rules[method]
                    rank = rule.score(feature[method](item, live, budget.remaining / cap))
                    if calendar.choose(rule, rank, day=day, previous=previous, remaining=budget.remaining):
                        target = live
        verdict = None
        if target is not None and budget.remaining and not quarantined:
            def invoke(proposed, old):
                verdict, sent, received, fresh, latency = ledger.call(
                    proposed, old, evidence.get(item.fact_id, ""), provider)
                metrics["fresh_requests"] += fresh
                metrics["latency_seconds"] += latency
                if sent is None:
                    metrics["unmetered_calls"] += 1
                else:
                    metrics["logical_input_tokens"] += sent
                    metrics["logical_output_tokens"] += received
                    if fresh:
                        metrics["fresh_input_tokens"] += sent
                        metrics["fresh_output_tokens"] += received
                return verdict

            failures = budget.failures
            verdict = budget.call(invoke, claim, target)
            if target == live:
                unverified = deepcopy(memory)
                _advance(unverified, "subject", item)
                _apply_verdict(memory, "subject", item, target, verdict)
                if budget.failures == failures:
                    def values(state):
                        return {f.value for f in state.retrieve("subject", claim.predicate, as_of=day)
                                if allowed(episode, f.fact_id, f.value)}
                    visits.append((item, values(unverified), values(memory)))
            else:
                metrics["stale_targets"] += 1
                _advance(memory, "subject", item)
        else:
            _advance(memory, "subject", item)
        decision_trace.append({"day": day.isoformat(), "candidate": item.fact_id, "eligible": eligible,
                               "live_target": live.fact_id if live else None,
                               "selected_target": target.fact_id if target else None, "rank": rank,
                               "future_forecast": forecast, "verdict": verdict, "calls": budget.attempts})
        snapshots[day] = deepcopy(memory)
    future = 0
    for entry in reversed(decision_trace):
        entry["future_observed"] = future
        future += entry["eligible"]
    metrics.update(calls=budget.attempts, verifier_failures=budget.failures)
    return memory, dict(metrics), quarantined, visits, decision_trace, snapshots


def visible(memory, episode, check):
    return tuple(f for f in memory.retrieve("subject", check.predicate, as_of=check.effective)
                 if f.source.observed_on <= check.observed and allowed(episode, f.fact_id, f.value))


def reader_evidence(memory, episode):
    return EvidenceIndexV2(tuple(
        Field(f.fact_id, f.source.reference, f.value, f.predicate, f.source.observed_on, f.valid_from, f.valid_to)
        for f in memory.retrieve("subject", None, as_of=episode.closing)
        if allowed(episode, f.fact_id, f.value)), signature(sorted(episode.permitted)))


def reader_outcome(reader, evidence, episode, gold, question):
    try:
        answer = reader(question, evidence, episode.closing)
    except (ProviderError, TimeoutError, ValueError, TypeError):
        return "invalid", 0
    if answer is None:
        return "missing", 0
    if not isinstance(answer, Answer):
        return "invalid", 0
    if answer.text is None:
        return ("invalid", 0) if answer.citations else ("abstained", int(not gold.answerable))
    candidates = evidence.retrieve("authorization check", episode.closing,
                                   lambda texts: [[1, 0] for _ in texts], k=len(episode.permitted))
    allowed_ids = {f.fact_id for f in evidence.materialize(candidates, "subject")}
    if not answer.citations or not set(answer.citations) <= allowed_ids:
        return "authorization-failure", 0
    return "answered", int(answer.text.strip() in gold.answers)


def evaluate(episode, gold, question, method, cap, mode, rules, feature, provider, ledger, reader):
    validate(episode, gold)
    memory, metrics, quarantine, visits, trace, snapshots = replay(
        episode, method, cap, mode, rules, feature, provider, ledger)
    def at(check):
        day = max((day for day in snapshots if day <= check.observed), default=None)
        state = snapshots[day] if day is not None else TemporalMemory()
        return {f.value for f in visible(state, episode, check)}

    checks = ([0] * len(gold.checks) if quarantine else [
        int(at(c) == set(c.values)) for c in gold.checks])
    scores = Counter()
    for c, correct in zip(gold.checks, checks, strict=True):
        scores[c.type] += correct
    helpful = evaluated_helpfulness = 0
    for item, without, with_verification in visits:
        for c in gold.checks:
            if (c.type == "current" and c.observed == item.source.observed_on
                    and c.predicate == item.claim.predicate and not quarantine):
                evaluated_helpfulness += 1
                helpful += without != set(c.values) and with_verification == set(c.values)
                break
    harmful = sum(t.fact_id in gold.harmful and t.operation in ("add", "supersede") for t in memory.trace)
    outcome, answer = (("authorization-failure", 0) if quarantine else
                       reader_outcome(reader, reader_evidence(memory, episode), episode, gold, question))
    return metrics | {"current": scores["current"], "current_total": 6,
                      "historical": scores["historical"], "historical_total": 5,
                      "reader": outcome, "reader_correct": answer, "reader_total": 1,
                      "helpful_verifications": helpful, "harmful_updates": harmful,
                      "helpfulness_evaluable": evaluated_helpfulness,
                      "quarantined": quarantine, "trace": trace}


def paired(contrasts):
    """Take two aligned sequences of family-level differences, one per endpoint."""
    if len(contrasts) != 2 or len(contrasts[0]) != len(contrasts[1]) or len(contrasts[0]) < 2:
        raise ValueError("Expected two contrasts over the same two or more families")
    rng = random.Random(BOOTSTRAP_SEED)
    draws = [[], []]
    size = len(contrasts[0])
    for _ in range(BOOTSTRAP_DRAWS):
        sample = rng.choices(range(size), k=size)
        for values, bootstrap in zip(contrasts, draws, strict=True):
            bootstrap.append(fmean(values[i] for i in sample))
    def q(values, p):
        coordinate = (len(values) - 1) * p
        index = int(coordinate)
        return values[index] + (coordinate - index) * (values[index + 1] - values[index])
    result = []
    for values, bootstrap in zip(contrasts, draws, strict=True):
        ordered = sorted(bootstrap)
        result.append((fmean(values), q(ordered, .0125), q(ordered, .9875)))
    return tuple(result)

def failed_condition():
    return {"current": 0, "current_total": 6, "historical": 0, "historical_total": 5,
            "reader": "missing", "reader_correct": 0, "reader_total": 1,
            "condition_status": "backend-failure"}


def summarize_primary(records):
    by_history = {}
    for row in records:
        if row["mode"] == "closed-loop" and row["cap"] == 2:
            key = row["family"], row["history"]
            methods = by_history.setdefault(key, {})
            if row["policy"] in methods or row["current_total"] != 6:
                raise ValueError("Primary rows must be unique with all six checks")
            methods[row["policy"]] = row["current"] / 6
    families = {}
    for (family, _), methods in sorted(by_history.items()):
        if set(methods) != set(POLICIES):
            raise ValueError("Missing planned primary condition")
        families.setdefault(family, []).append((methods["T2"] - methods["B3"],
                                                methods["T2"] - methods["H-paced"]))
    return paired([[fmean(row[k] for row in values) for values in families.values()] for k in (0, 1)])


def run_reviewed(cases, receipt, output, *, rules, feature, provider, reader):
    """Resume at case-condition boundaries after a separately approved manifest."""
    output = Path(output)
    if Path("results").resolve() not in output.resolve().parents:
        raise ValueError("Use a new ignored results directory")
    cases = sorted(cases, key=lambda c: (c[0].family, c[0].identity))
    cohort = Counter(c[0].family for c in cases)
    if (len(cohort) != 90 or any(n != 4 for n in cohort.values())
            or len({c[0].identity for c in cases}) != len(cases)):
        raise ValueError("The current protocol requires 90 reviewed families of four unique histories")
    content = signature([(asdict(episode), asdict(gold), question) for episode, gold, question in cases])
    parties = ("fixture_author", "independent_reviewer", "project_approver")
    identities = [receipt.get(n) for n in parties]
    if (receipt.get("status") != "approved" or receipt.get("cohort_sha256") != content
            or not all(isinstance(name, str) and name.strip() for name in identities)
            or len({name.strip().casefold() for name in identities}) != len(parties)
            or any(not isinstance(receipt.get(k), str) or not receipt[k].strip()
                   for k in ("protocol_sha256", "backend_fingerprint", "code_sha256"))):
        raise ValueError("Missing external review, project approval or executable freeze")
    if receipt["code_sha256"] != code_fingerprint():
        raise ValueError("Executable freeze does not match this replay implementation")
    for episode, gold, question in cases:
        validate(episode, gold)
        support = dict(episode.support)
        values = {item.fact_id: item.claim.value for item in episode.events}
        if (len(support) != len(episode.support) or set(support) != episode.permitted
                or any(values[key] not in value or not allowed(episode, key, value)
                       for key, value in support.items())):
            raise ValueError("Approved source spans incomplete or not authorized")
        if not question.strip() or any(v.casefold() in question.casefold() for v in episode.restricted_values):
            raise ValueError("Missing reader question or restricted query text")
    # A receipt records evidence supplied by people. This function cannot authenticate identities.
    output.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(output / "conditions.sqlite")) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS freeze (fingerprint TEXT PRIMARY KEY)")
        db.execute("CREATE TABLE IF NOT EXISTS results (key TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        lock = signature([VERSION, receipt])
        existing = db.execute("SELECT fingerprint FROM freeze").fetchone()
        if existing and existing[0] != lock:
            raise ValueError("Cannot resume with a different approval receipt")
        db.execute("INSERT OR IGNORE INTO freeze VALUES (?)", (lock,))
        db.commit()
        ledger = ExactLedger(output / "verifier.sqlite", receipt["backend_fingerprint"])
        rows = []
        for episode, gold, question in cases:
            for mode in ("closed-loop", "fixed"):
                for cap in CAPS:
                    for policy in POLICIES:
                        key = signature([episode.identity, mode, cap, policy])
                        cached = db.execute("SELECT payload FROM results WHERE key=?", (key,)).fetchone()
                        if cached:
                            row = json.loads(cached[0])
                        else:
                            try:
                                row = evaluate(episode, gold, question, policy, cap, mode,
                                               rules, feature, provider, ledger, reader)
                            except (ProviderError, TimeoutError):
                                row = failed_condition()
                            row.update(history=episode.identity, family=episode.family, mode=mode,
                                       cap=cap, policy=policy)
                            db.execute("INSERT INTO results VALUES (?,?)", (key, json.dumps(row)))
                            db.commit()
                        rows.append(row)
    return rows, summarize_primary(rows)


def code_fingerprint():
    files = ("validation_v2.py", "causal_horizon_v1.py", "adaptive_verification.py",
             "baselines.py", "evidence_index_v2.py", "memory.py", "verification.py")
    folder = Path(__file__).resolve().parent
    return signature({name: sha256((folder / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                      for name in files})
