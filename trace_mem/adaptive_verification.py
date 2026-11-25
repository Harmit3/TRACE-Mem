"""Versioned online allocation over frozen verification utility scores."""

from collections.abc import Callable
from dataclasses import dataclass
import math


def neutralized_score(model, vector):
    """Compare candidates at a common budget coordinate."""
    return model.controller.score((*vector[:-1], 1.0))


def heuristic_score(vector):
    """Prioritize implicit asserted changes that B2 would defer."""
    uncertainty = vector[6]
    return (0.55 if uncertainty == 0.5 else 0.25 if uncertainty == 1 else 0.0
            ) + 0.15 * vector[3] + 0.10 * vector[5]


@dataclass(frozen=True)
class AdaptiveAllocation:
    score: Callable[[tuple[float, ...]], float]
    reference: tuple[float, ...]
    planned_candidates: int

    def __post_init__(self):
        if (type(self.planned_candidates) is not int or self.planned_candidates < 1
                or not self.reference or tuple(sorted(self.reference)) != self.reference
                or not all(math.isfinite(value) for value in self.reference)):
            raise ValueError("Expected a positive planning horizon and finite sorted reference scores")

    def choose(self, score, *, remaining, seen):
        """Use only today's opportunity, spent budget and an exogenous horizon."""
        if not math.isfinite(score) or seen < 1 or remaining < 0:
            raise ValueError("Invalid online allocation state")
        if remaining == 0:
            return False
        horizon_remaining = max(1, self.planned_candidates - seen + 1)
        if remaining >= horizon_remaining:
            return True
        fraction = remaining / horizon_remaining
        index = min(len(self.reference) - 1, math.ceil((1 - fraction) * len(self.reference)) - 1)
        # Compare the candidate to the upper-tail boundary. Ties are accepted in arrival order.
        return score >= self.reference[index]
