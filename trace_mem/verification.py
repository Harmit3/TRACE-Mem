"""Verifier call accounting and deterministic fixed-stream selection."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import math
import random
from typing import Literal

from trace_mem.claims import Claim
from trace_mem.memory import Fact


Verdict = Literal["same", "update", "historical", "unrelated", "insufficient_evidence"]


@dataclass(slots=True)
class Budget:
    limit: int
    attempts: int = 0
    failures: int = 0

    def __post_init__(self) -> None:
        if type(self.limit) is not int or self.limit < 0 or self.attempts or self.failures:
            raise ValueError("Expected a nonnegative limit and fresh counters")

    @property
    def remaining(self) -> int:
        return self.limit - self.attempts

    def call(self, verify: Callable[[Claim, Fact], Verdict], claim: Claim, fact: Fact) -> Verdict:
        if self.remaining <= 0:
            raise RuntimeError("Verification budget exhausted")
        self.attempts += 1
        try:
            verdict = verify(claim, fact)
            if verdict not in ("same", "update", "historical", "unrelated", "insufficient_evidence"):
                raise ValueError("Unknown verifier verdict")
        except Exception:
            self.failures += 1
            return "insufficient_evidence"
        return verdict


def select_random(count: int, calls: int, *, seed: int) -> frozenset[int]:
    """B4 selection on a frozen candidate stream."""
    _validate_target(count, calls)
    return frozenset(random.Random(seed).sample(range(count), calls))


def select_ranked(scores: Sequence[float], calls: int) -> frozenset[int]:
    """B5 or learned-score selection with chronological tie-breaking."""
    _validate_target(len(scores), calls)
    if any(not math.isfinite(score) for score in scores):
        raise ValueError("Scores must be finite")
    order = sorted(range(len(scores)), key=lambda index: (-scores[index], index))
    return frozenset(order[:calls])


def _validate_target(count: int, calls: int) -> None:
    if type(count) is not int or type(calls) is not int or not 0 <= calls <= count:
        raise ValueError("Verification target must fit the candidate stream")
