"""Train a deterministic logistic scorer on independently annotated decisions."""

from collections.abc import Sequence
from dataclasses import dataclass
import math
from statistics import fmean, pstdev


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

    def score(self, features: Sequence[float]) -> float:
        if len(features) != len(self.weights) or any(not math.isfinite(x) for x in features):
            raise ValueError("Feature vector has an invalid width or value")
        return _sigmoid(self.intercept + sum(
            weight * (value - mean) / scale
            for value, mean, scale, weight in zip(features, self.means, self.scales, self.weights)
        ))


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
    if steps <= 0 or not math.isfinite(learning_rate) or learning_rate <= 0:
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
