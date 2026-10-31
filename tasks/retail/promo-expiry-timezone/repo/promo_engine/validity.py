"""Promotion validity windows.

A promotion is active from the start of `starts_on` until the end of
`expires_on`, both evaluated on the store's local calendar.
"""

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .models import Promotion


def promo_window(promo: Promotion, tz: ZoneInfo):
    """Return the (start, end) instants of the promotion as UTC datetimes.

    `start` is inclusive, `end` is exclusive.
    """
    offset = tz.utcoffset(datetime.combine(promo.starts_on, time(12)))
    start = datetime.combine(promo.starts_on, time.min) - offset
    length = timedelta(days=(promo.expires_on - promo.starts_on).days)
    end = start + length + timedelta(hours=23, minutes=59, seconds=59)
    return start.replace(tzinfo=timezone.utc), end.replace(tzinfo=timezone.utc)


def is_active(promo: Promotion, at: datetime, tz: ZoneInfo) -> bool:
    """True if the promotion is active at instant `at` for a store in zone `tz`."""
    start, end = promo_window(promo, tz)
    return start <= at.astimezone(timezone.utc) < end


def days_remaining(promo: Promotion, at: datetime, tz: ZoneInfo) -> int:
    """Calendar days left after today (store-local) - shown on shelf labels.

    0 on the last day of the promotion and afterwards.
    """
    today = at.astimezone(timezone.utc).date()
    return max(0, (promo.expires_on - today).days)
