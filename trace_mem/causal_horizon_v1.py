"""Causal calendar-exposure wrapper around frozen adaptive pacing."""
from dataclasses import dataclass, replace
from datetime import date
from fractions import Fraction

from trace_mem.adaptive_verification import AdaptiveAllocation


VERSION = "gamma-calendar-v1"
# Step 23 development: 20 arrivals over two six-day windows. One half-history of prior exposure.
PRIOR_ARRIVALS = 5
PRIOR_DAYS = 3
MAX_FUTURE = 20


@dataclass(frozen=True)
class CalendarPlanner:
    opening: date
    closing: date
    numerator: int = 1
    denominator: int = 1

    def __post_init__(self):
        if self.closing < self.opening or (self.numerator, self.denominator) not in {
                (1, 2), (1, 1), (2, 1)}:
            raise ValueError("Invalid calendar or stress ratio")

    def future(self, day, previous):
        if (not self.opening <= day <= self.closing or type(previous) is not int or previous < 0):
            raise ValueError("Invalid observed arrival state")
        exposure = (day - self.opening).days
        remaining = (self.closing - day).days
        mean = Fraction((PRIOR_ARRIVALS + previous) * remaining * self.numerator,
                        (PRIOR_DAYS + exposure) * self.denominator)
        rounded = int(mean + Fraction(1, 2))
        return min(MAX_FUTURE, rounded)

    def choose(self, rule: AdaptiveAllocation, score, *, day, previous, remaining):
        seen = previous + 1
        nominal = seen + self.future(day, previous)
        return replace(rule, planned_candidates=nominal).choose(score, remaining=remaining, seen=seen)
