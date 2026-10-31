"""Utility holiday calendar: holidays are billed off-peak all day."""

from datetime import date, timedelta


def _nth_weekday(year, month, weekday, n):
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(year, month, weekday):
    d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def utility_holidays(year):
    return frozenset({
        date(year, 1, 1),
        _last_weekday(year, 5, 0),          # Memorial Day
        date(year, 7, 4),
        _nth_weekday(year, 9, 0, 1),        # Labor Day
        _nth_weekday(year, 11, 3, 4),       # Thanksgiving
        date(year, 12, 25),
    })
