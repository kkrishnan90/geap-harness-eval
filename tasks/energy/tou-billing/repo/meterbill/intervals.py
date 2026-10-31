from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

INTERVAL = timedelta(minutes=15)


@dataclass(frozen=True)
class Interval:
    start: datetime   # timezone-aware, UTC
    kwh: Decimal

    def __post_init__(self):
        if self.start.tzinfo is None:
            raise ValueError("interval start must be timezone-aware")

    @property
    def end(self):
        return self.start + INTERVAL


def utc(y, mo, d, h=0, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)
