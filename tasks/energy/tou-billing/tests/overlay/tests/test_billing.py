import unittest
from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from meterbill import RESIDENTIAL_TOU_2026, compute_bill
from meterbill.billing import band_for

from .helpers import local_day_intervals, period_intervals

ZONE = RESIDENTIAL_TOU_2026.zone
CHI = ZoneInfo(ZONE)


class BandTest(unittest.TestCase):
    def test_weekday_bands(self):
        t = RESIDENTIAL_TOU_2026
        self.assertEqual(band_for(t, datetime(2026, 1, 14, 3, 0)).code, "OFFPEAK")
        self.assertEqual(band_for(t, datetime(2026, 1, 14, 7, 0)).code, "SHOULDER")
        self.assertEqual(band_for(t, datetime(2026, 1, 14, 17, 45)).code, "PEAK")
        self.assertEqual(band_for(t, datetime(2026, 1, 14, 21, 0)).code, "SHOULDER")
        self.assertEqual(band_for(t, datetime(2026, 1, 14, 23, 45)).code, "OFFPEAK")

    def test_weekend_offpeak(self):
        self.assertEqual(band_for(RESIDENTIAL_TOU_2026, datetime(2026, 1, 17, 17, 0)).code, "OFFPEAK")


class JanuaryBillTest(unittest.TestCase):
    """Winter month: no DST change, flat 0.25 kWh per interval."""

    def setUp(self):
        self.ivs = period_intervals(ZONE, date(2026, 1, 1), date(2026, 1, 31))
        self.bill = compute_bill(RESIDENTIAL_TOU_2026, self.ivs, date(2026, 1, 1), date(2026, 1, 31))

    def test_line_order(self):
        self.assertEqual([l.code for l in self.bill.lines], ["PEAK", "SHOULDER", "OFFPEAK", "DAILY"])

    def test_energy_quantities(self):
        # 21 working days in Jan 2026 (Jan 1 holiday not configured in this tariff -> 22 weekdays)
        weekdays = sum(1 for d in range(1, 32) if date(2026, 1, d).weekday() < 5)
        self.assertEqual(self.bill.line("PEAK").quantity, Decimal("4.0") * weekdays)
        self.assertEqual(self.bill.line("SHOULDER").quantity, Decimal("11.0") * weekdays)
        total = sum(l.quantity for l in self.bill.lines[:3])
        self.assertEqual(total, Decimal("0.25") * len(self.ivs))

    def test_daily_charge(self):
        daily = self.bill.line("DAILY")
        self.assertEqual(daily.quantity, 31)
        self.assertEqual(daily.amount, Decimal("15.29"))

    def test_total_is_sum_of_lines(self):
        self.assertEqual(self.bill.total, sum(l.amount for l in self.bill.lines))
        self.assertEqual(self.bill.line("PEAK").amount, Decimal("25.01"))

    def test_intervals_outside_period_ignored(self):
        extra = local_day_intervals(ZONE, date(2026, 2, 1))
        bill = compute_bill(RESIDENTIAL_TOU_2026, self.ivs + extra, date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(bill.lines, self.bill.lines)


class HolidayTest(unittest.TestCase):
    def test_holiday_offpeak(self):
        import dataclasses
        from meterbill.holidays import utility_holidays
        t = dataclasses.replace(RESIDENTIAL_TOU_2026, holidays=utility_holidays(2026))
        bill = compute_bill(t, local_day_intervals(ZONE, date(2026, 1, 1)), date(2026, 1, 1), date(2026, 1, 1))
        self.assertEqual(bill.line("PEAK").quantity, 0)
        self.assertEqual(bill.line("OFFPEAK").quantity, Decimal("24"))


if __name__ == "__main__":
    unittest.main()
