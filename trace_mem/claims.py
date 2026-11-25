"""Structured claim extraction boundary and deterministic conflict detection."""

from dataclasses import dataclass, field
from datetime import date
import json
from typing import Callable, Literal

from trace_mem.data.memora import Event
from trace_mem.memory import Fact, TemporalMemory


@dataclass(frozen=True, slots=True)
class Claim:
    predicate: str
    value: str
    intent: Literal["assert", "correct", "uncertain", "delete"]
    effective_on: date
    expires_on: date | None = None
    explicit_effective_date: bool = field(default=False, compare=False)


EXTRACTION_PROMPT = (
    'Extract claims from the user message as a JSON array. Each claim has "predicate", '
    '"value", and "intent" (assert, correct, uncertain, delete). Include ISO dates '
    '"effective_on" and exclusive "expires_on" only if specified. Omit unspecified dates. '
    "Use job for employment, residence for home, and visit for a temporary trip. "
    'Example: "I switched employers to North Office" -> '
    '[{"predicate":"job","value":"North Office","intent":"correct"}]. '
    'Example: "I might join North Office next month" -> '
    '[{"predicate":"job","value":"North Office","intent":"uncertain"}]. '
    "Do not invent claims, dates, or updates. Return only the JSON array."
)


def extract(event: Event, complete: Callable[[str, str], str]) -> tuple[Claim, ...]:
    """Use an injected completion backend with a structured, validated contract."""
    if event.role != "user":
        return ()
    payload = json.dumps({"observed_on": event.observed_on.isoformat(), "message": event.message})
    return parse_claims(complete(EXTRACTION_PROMPT, payload), event.observed_on)


def parse_claims(text: str, observed_on: date) -> tuple[Claim, ...]:
    rows = json.loads(text)
    if not isinstance(rows, list):
        raise ValueError("Claim extraction requires a JSON array")
    claims = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each claim must be an object")
        predicate, value, intent = (row.get(key) for key in ("predicate", "value", "intent"))
        if not all(isinstance(item, str) and item.strip() for item in (predicate, value, intent)):
            raise ValueError("Claim predicate, value and intent are required")
        if intent not in ("assert", "correct", "uncertain", "delete"):
            raise ValueError("Unknown claim intent")
        start = date.fromisoformat(row.get("effective_on") or observed_on.isoformat())
        end = date.fromisoformat(row["expires_on"]) if row.get("expires_on") else None
        if end is not None and end <= start:
            raise ValueError("Claim expiry must follow its start")
        claims.append(Claim(predicate.strip().casefold(), value.strip(), intent, start, end,
                            explicit_effective_date=bool(row.get("effective_on"))))
    return tuple(claims)


def conflicts(memory: TemporalMemory, entity: str, claim: Claim) -> tuple[Fact, ...]:
    """Compare competing values under the same predicate and effective date."""
    return tuple(fact for fact in memory.retrieve(entity, claim.predicate, as_of=claim.effective_on)
                 if fact.value.casefold() != claim.value.casefold())
