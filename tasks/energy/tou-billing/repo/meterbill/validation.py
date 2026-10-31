"""Interval data quality checks run before billing (VEE - validation step only)."""

from dataclasses import dataclass
from decimal import Decimal
from typing import List

from .intervals import INTERVAL


@dataclass(frozen=True)
class Issue:
    kind: str       # GAP | NEGATIVE | DUPLICATE | MISALIGNED
    start: object
    detail: str = ""


def check_intervals(intervals) -> List[Issue]:
    issues = []
    seen = set()
    ordered = sorted(intervals, key=lambda i: i.start)
    for iv in ordered:
        if iv.start.minute % 15 or iv.start.second:
            issues.append(Issue("MISALIGNED", iv.start))
        if iv.kwh < Decimal("0"):
            issues.append(Issue("NEGATIVE", iv.start, str(iv.kwh)))
        if iv.start in seen:
            issues.append(Issue("DUPLICATE", iv.start))
        seen.add(iv.start)
    starts = sorted(seen)
    for a, b in zip(starts, starts[1:]):
        if b - a > INTERVAL:
            issues.append(Issue("GAP", a + INTERVAL, f"{int((b - a) / INTERVAL) - 1} intervals"))
    return issues
