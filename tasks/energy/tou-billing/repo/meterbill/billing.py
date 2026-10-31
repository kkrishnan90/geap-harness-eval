"""Bill computation for TOU tariffs."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import List
from zoneinfo import ZoneInfo

CENT = Decimal("0.01")


@dataclass(frozen=True)
class BillLine:
    code: str
    description: str
    quantity: Decimal      # kWh for energy lines, days for the daily charge
    unit_price: Decimal
    amount: Decimal        # rounded to cents


@dataclass(frozen=True)
class Bill:
    tariff: str
    first_day: object      # date (local), inclusive
    last_day: object       # date (local), inclusive
    lines: List[BillLine]

    @property
    def total(self):
        return sum((l.amount for l in self.lines), Decimal("0"))

    def line(self, code):
        for l in self.lines:
            if l.code == code:
                return l
        raise KeyError(code)


def _in_window(t, start, end):
    if end == time(0):
        return t >= start
    return start <= t < end


def band_for(tariff, local_dt):
    """Band of an interval starting at local_dt (local wall clock)."""
    is_working_day = local_dt.weekday() < 5 and local_dt.date() not in tariff.holidays
    for band in tariff.bands:
        if band.weekdays_only and not is_working_day:
            continue
        for start, end in band.windows:
            if _in_window(local_dt.time(), start, end):
                return band
    return tariff.default_band


def compute_bill(tariff, intervals, first_day, last_day):
    """Bill for local days first_day..last_day (inclusive).

    Lines: one energy line per band in tariff order (bands, then default band),
    followed by the DAILY fixed-charge line.
    """
    zone = ZoneInfo(tariff.zone)
    period_start = datetime.combine(first_day, time(0), tzinfo=zone)
    offset = period_start.utcoffset()

    usage = {b.code: 0.0 for b in tariff.all_bands}
    n = 0
    for iv in intervals:
        local = (iv.start + offset).replace(tzinfo=None)
        if not first_day <= local.date() <= last_day:
            continue
        usage[band_for(tariff, local).code] += float(iv.kwh)
        n += 1

    lines = []
    for band in tariff.all_bands:
        kwh = usage[band.code]
        amount = Decimal(str(round(kwh * float(band.rate), 2)))
        lines.append(BillLine(band.code, band.description,
                              Decimal(str(round(kwh, 3))), band.rate, amount))
    days = n // 96
    lines.append(BillLine("DAILY", "Daily supply charge", Decimal(days), tariff.daily_charge,
                          Decimal(str(round(days * float(tariff.daily_charge), 2)))))
    return Bill(tariff.code, first_day, last_day, lines)
