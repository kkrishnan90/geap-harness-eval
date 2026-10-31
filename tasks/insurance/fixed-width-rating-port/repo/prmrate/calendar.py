"""Run-date helpers shared with the scheduler (unrelated to rating rules)."""

from datetime import date, timedelta


def parse_run_date(text):
    """PIC 9(8) YYYYMMDD -> date."""
    if len(text) != 8 or not text.isdigit():
        raise ValueError(f"bad run date {text!r}")
    return date(int(text[:4]), int(text[4:6]), int(text[6:]))


def next_business_day(d, holidays=frozenset()):
    d = d + timedelta(days=1)
    while d.weekday() >= 5 or d in holidays:
        d = d + timedelta(days=1)
    return d


def renewal_window(run_date, days_ahead=30):
    """Policies expiring in (run_date, run_date + days_ahead] are picked up for renewal."""
    return run_date + timedelta(days=1), run_date + timedelta(days=days_ahead)
