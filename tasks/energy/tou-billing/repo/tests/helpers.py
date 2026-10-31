from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from meterbill import Interval


def local_day_intervals(zone, day, kwh=lambda local: Decimal("0.250")):
    """All 15-minute intervals of one local day (92/96/100 of them), UTC starts."""
    tz = ZoneInfo(zone)
    start = datetime.combine(day, time(0), tzinfo=tz).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time(0), tzinfo=tz).astimezone(timezone.utc)
    out = []
    t = start
    while t < end:
        out.append(Interval(t, kwh(t.astimezone(tz))))
        t += timedelta(minutes=15)
    return out


def period_intervals(zone, first, last, kwh=lambda local: Decimal("0.250")):
    out = []
    d = first
    while d <= last:
        out.extend(local_day_intervals(zone, d, kwh))
        d += timedelta(days=1)
    return out
