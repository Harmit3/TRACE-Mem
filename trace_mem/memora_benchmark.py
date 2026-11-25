"""Answer-blind local Memora replay; fixed-stream allocation and causal policies."""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import random
import re

from trace_mem.baselines import _apply, _apply_verdict, _eligible_target, _prepare
from trace_mem.data.memora import Event
from trace_mem.llm_tasks import LLMTasks
from trace_mem.memory import TemporalMemory
from trace_mem.providers import LimitExceeded, ProviderError
from trace_mem.semantic import retrieve_semantic
from trace_mem.verification import Budget, select_random, select_ranked


METHODS = ("B0", "B1", "B2", "B3", "B4", "B5", "T1", "T1-no-NLI")
YEAR_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


@dataclass(frozen=True)
class Question:
    identifier: str
    task: str
    text: str
    observed_on: date

    @property
    def as_of(self) -> date:
        dates = YEAR_DATE.findall(self.text)
        if len(dates) == 1:
            try:
                return min(date.fromisoformat(dates[0]), self.observed_on)
            except ValueError:
                pass
        return self.observed_on


def questions(path: Path, selectors: dict[str, list[int]]) -> tuple[Question, ...]:
    """Project only selected public query fields. Never return rubric or evidence."""
    groups = json.loads(path.read_bytes())["questions"]
    projected = []
    for task, indices in sorted(selectors.items()):
        for index in indices:
            row = groups[task][index]
            projected.append(Question(row["question_id"], task, row["question"],
                                      date.fromisoformat(row["question_date"])))
    if len({q.identifier for q in projected}) != len(projected):
        raise ValueError("Duplicate question identifier")
    return tuple(projected)


def prepare(events: Iterable[Event], tasks: LLMTasks):
    failures = Counter()

    def complete(prompt, payload):
        try:
            return tasks.complete(prompt, payload)
        except LimitExceeded:
            raise
        except ProviderError:
            failures["extract"] += 1
            return "[]"

    return tuple(_prepare(events, complete)), dict(failures)


def _advance(memory, entity, item, method="B2"):
    _apply(memory, entity, item.claim, item.source, item.fact_id, method, None, None, None)


def _score(model, builder, item, target, entity, remaining):
    vector = builder(item.claim, target, entity=entity, source=item.source,
                     budget_remaining_fraction=remaining)
    if vector[1] is None:
        # The padded no-NLI artifact ignores this slot. Fail closed for any other artifact.
        if model.controller.weights[1] != 0:
            raise ValueError("Only an NLI-independent controller can omit contradiction")
        vector = (*vector[:1], 0.0, *vector[2:])
    return model.controller.score(vector)


def run_suite(events, prepared, tasks, *, entity, models, builders, mode, cap,
              seed, random_probability=0.25):
    """Replay all policies over one observation cutoff with identical prepared claims."""
    if (mode not in {"fixed", "closed-loop"} or type(cap) is not int or cap < 0
            or not 0 <= random_probability <= 1):
        raise ValueError("Invalid replay mode or verification budget")
    evidence = {(event.session_id, event.turn): event.message for event in events
                if event.role == "user"}

    def frozen_candidates():
        memory = TemporalMemory()
        candidates = []
        for item in prepared:
            target = _eligible_target(memory, entity, item.claim)
            if target is not None:
                candidates.append((item, target))
            _advance(memory, entity, item)
        return candidates

    candidates = frozen_candidates() if mode == "fixed" else ()
    matched = min(len(candidates), cap)
    frozen_pool = {item.fact_id: target for item, target in candidates}
    output = {}
    for method in METHODS:
        memory = TemporalMemory()
        budget = Budget(cap if method not in {"B0", "B1", "B2"} else 0)
        rng = random.Random(seed)
        selected = {}
        if mode == "fixed" and budget.limit:
            if method in {"B3", "B4"}:
                indices = (range(len(candidates)) if method == "B3"
                           else select_random(len(candidates), matched, seed=seed))
            else:
                scores = ([{"uncertain": 1, "assert": 0.5, "correct": 0}[item.claim.intent]
                           for item, _ in candidates] if method == "B5" else
                          [_score(models[method], builders[method], item, target, entity, 1.0)
                           for item, target in candidates])
                indices = select_ranked(scores, matched)
            selected = {candidates[i][0].fact_id: candidates[i][1] for i in indices}

        stale = eligible = 0
        for item in prepared if method != "B0" else ():
            live = (_eligible_target(memory, entity, item.claim)
                    if method not in {"B1", "B2"} else None)
            if mode == "fixed":
                eligible += item.fact_id in frozen_pool
                target = selected.get(item.fact_id)
            else:
                eligible += live is not None
                target = None
                if live is not None and budget.remaining:
                    intent = item.claim.intent
                    if (method == "B3"
                            or method == "B4" and rng.random() < random_probability
                            or method == "B5" and intent == "uncertain"
                            or method in models and _score(
                                models[method], builders[method], item, live, entity,
                                budget.remaining / budget.limit) >= models[method].threshold):
                        target = live
            if target is not None and budget.remaining:
                session, turn = map(int, item.source.reference.split("/"))
                # Prior user text is intentionally excluded to avoid resurfacing deleted evidence.
                conversation = (evidence[session, turn],)
                verdict = budget.call(lambda claim, fact: tasks.verify(
                    claim, fact, conversation=conversation), item.claim, target)
                if live is not None and live == target:
                    _apply_verdict(memory, entity, item, live, verdict)
                    continue
                stale += 1
            _advance(memory, entity, item, "B1" if method == "B1" else "B2")
        output[method] = (memory, {"budget_cap": budget.limit, "verification_attempts": budget.attempts,
                                   "verification_failures": budget.failures, "stale_targets": stale,
                                   "eligible_candidates": eligible})
    return output


def answer_suite(question, states, tasks, *, entity, k, embed):
    output = {}
    for method, (memory, stats) in states.items():
        facts = [hit.fact for hit in retrieve_semantic(
            memory, question.text, entity=entity, as_of=question.as_of, k=k, embed=embed)]
        # Bound variable reader evidence while preserving ranked order.
        retained = []
        remaining = max(0, 3000 - len(json.dumps(question.text).encode()))
        for fact in facts:
            size = len(json.dumps((fact.fact_id, fact.predicate, fact.value)).encode())
            if size <= remaining:
                retained.append(fact)
                remaining -= size
        try:
            answer = tasks.answer_from_facts(question.text, retained, as_of=question.as_of)
            response = {"answer": answer.text, "citations": answer.citations, "reader_error": False}
        except LimitExceeded:
            raise
        except ProviderError:
            response = {"answer": None, "citations": (), "reader_error": True}
        output[method] = {**response, **stats, "retrieved": len(retained),
                          "transitions": dict(Counter(item.operation for item in memory.trace))}
    return output
