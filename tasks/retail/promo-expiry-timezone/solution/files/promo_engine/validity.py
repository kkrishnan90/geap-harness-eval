"""Promotion validity windows.

A promotion is active from the start of `starts_on` until the end of
`expires_on`, both evaluated on the store's local calendar.
"""

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .models import Promotion


def _require_aware(at: datetime) -> None:
    if at.tzinfo is None or at.tzinfo.utcoffset(at) is None:
        raise ValueError("`at` must be a timezone-aware datetime")


def _local_midnight_utc(day, tz: ZoneInfo) -> datetime:
    # Wall-clock midnight in the store zone, resolved by zoneinfo for that very date
    # (so the offset in force on that date is used, not the one at promotion start).
    return datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc)


def promo_window(promo: Promotion, tz: ZoneInfo):
    """Return the (start, end) instants of the promotion as UTC datetimes.

    `start` is inclusive, `end` is exclusive.
    """
    start = _local_midnight_utc(promo.starts_on, tz)
    end = _local_midnight_utc(promo.expires_on + timedelta(days=1), tz)
    return start, end


def is_active(promo: Promotion, at: datetime, tz: ZoneInfo) -> bool:
    """True if the promotion is active at instant `at` for a store in zone `tz`."""
    _require_aware(at)
    start, end = promo_window(promo, tz)
    return start <= at.astimezone(timezone.utc) < end


def days_remaining(promo: Promotion, at: datetime, tz: ZoneInfo) -> int:
    """Calendar days left after today (store-local) - shown on shelf labels.

    0 on the last day of the promotion and afterwards.
    """
    _require_aware(at)
    today = at.astimezone(tz).date()
    return max(0, (promo.expires_on - today).days)
