"""Train a deterministic logistic scorer on independently annotated decisions."""

from collections.abc import Sequence
from dataclasses import dataclass
import math
import re
from statistics import fmean, pstdev

from trace_mem.claims import Claim
from trace_mem.memory import Fact, Source
from trace_mem.semantic import SemanticEvidence, fact_text


FEATURE_NAMES = (
    "semantic_similarity", "contradiction_score", "entity_match",
    "temporal_conflict_score", "time_gap", "provenance_score",
    "uncertainty", "budget_remaining_fraction",
)


def features_for(
    claim: Claim,
    target: Fact,
    *,
    entity: str,
    source: Source,
    budget_remaining_fraction: float,
    semantic: SemanticEvidence | None = None,
) -> tuple[float, ...]:
    """Build the ordered T1 vector with optional local model evidence."""
    if not math.isfinite(budget_remaining_fraction) or not 0 <= budget_remaining_fraction <= 1:
        raise ValueError("Remaining budget fraction must be between zero and one")
    if claim.intent not in ("assert", "correct", "uncertain"):
        raise ValueError("Only non-deletion claims can be scored for verification")
    gap = (source.observed_on - target.source.observed_on).days
    if gap < 0:
        raise ValueError("Target evidence cannot come from a future observation")
    if not all((entity, claim.predicate, claim.value, target.entity, target.predicate, target.value)):
        raise ValueError("Entity, predicate and value are required for T1 features")

    same_entity = entity == target.entity
    competes = (same_entity and claim.predicate == target.predicate
                and claim.value.casefold() != target.value.casefold())
    overlaps = ((target.valid_to is None or claim.effective_on < target.valid_to)
                and (claim.expires_on is None or target.valid_from < claim.expires_on))
    uncertainty = {"correct": 0.0, "assert": 0.5, "uncertain": 1.0}[claim.intent]
    if semantic is None:
        left = set(re.findall(r"\w+", claim.value.casefold()))
        right = set(re.findall(r"\w+", target.value.casefold()))
        union = left | right
        similarity = len(left & right) / len(union) if union else float(claim.value == target.value)
        contradiction = float(competes) * (1.0 - uncertainty / 2)
    else:
        similarity, relation = semantic.compare(
            fact_text(target.entity, target.predicate, target.value),
            fact_text(entity, claim.predicate, claim.value),
        )
        contradiction = relation.contradiction
    return (
        similarity,
        contradiction,
        float(same_entity),
        float(competes and overlaps),
        float(gap),
        (bool(source.reference) + bool(target.source.reference)) / 2,
        uncertainty,
        budget_remaining_fraction,
    )


def _sigmoid(logit: float) -> float:
    if logit >= 0:
        return 1 / (1 + math.exp(-logit))
    exp = math.exp(logit)
    return exp / (1 + exp)


@dataclass(frozen=True, slots=True)
class LogisticController:
    means: tuple[float, ...]
    scales: tuple[float, ...]
    weights: tuple[float, ...]
    intercept: float

    def __post_init__(self) -> None:
        if not self.weights or len(self.means) != len(self.weights) or len(self.scales) != len(self.weights):
            raise ValueError("Controller parameters must share a nonzero width")
        if any(not math.isfinite(x) for x in (*self.means, *self.scales, *self.weights, self.intercept)):
            raise ValueError("Controller parameters must be finite")
        if any(scale <= 0 for scale in self.scales):
            raise ValueError("Controller scales must be positive")

    def score(self, features: Sequence[float]) -> float:
        if len(features) != len(self.weights) or any(not math.isfinite(x) for x in features):
            raise ValueError("Feature vector has an invalid width or value")
        logit = self.intercept + sum(
            weight * (value - mean) / scale
            for value, mean, scale, weight in zip(features, self.means, self.scales, self.weights)
        )
        if not math.isfinite(logit):
            raise ValueError("Controller produced a nonfinite logit")
        return _sigmoid(logit)


def fit(
    rows: Sequence[Sequence[float]],
    labels: Sequence[int],
    *,
    steps: int = 500,
    learning_rate: float = 0.1,
    l2: float = 0.01,
) -> LogisticController:
    """Fit a regularized model using training rows only. Missing features fail."""
    if not rows or len(rows) != len(labels) or set(labels) != {0, 1}:
        raise ValueError("Training requires matching rows and both binary classes")
    if type(steps) is not int or steps <= 0 or not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("Optimizer steps and learning rate must be positive")
    if not math.isfinite(l2) or l2 < 0:
        raise ValueError("Regularization must be finite and nonnegative")
    width = len(rows[0])
    if not width or any(len(row) != width or any(not math.isfinite(x) for x in row)
                        for row in rows):
        raise ValueError("Training features must be finite and have one nonzero width")

    columns = tuple(zip(*rows))
    means = tuple(fmean(column) for column in columns)
    scales = tuple(pstdev(column) or 1.0 for column in columns)
    normalized = [tuple((x - mean) / scale for x, mean, scale in zip(row, means, scales))
                  for row in rows]
    weights = [0.0] * width
    intercept = 0.0
    for _ in range(steps):
        errors = [_sigmoid(intercept + sum(w * x for w, x in zip(weights, row))) - label
                  for row, label in zip(normalized, labels)]
        gradient = [fmean(error * row[i] for error, row in zip(errors, normalized))
                    + l2 * weights[i] for i in range(width)]
        weights = [weight - learning_rate * delta for weight, delta in zip(weights, gradient)]
        intercept -= learning_rate * fmean(errors)
    return LogisticController(means, scales, tuple(weights), intercept)
