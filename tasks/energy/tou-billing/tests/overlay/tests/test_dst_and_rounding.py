import dataclasses
import unittest
from datetime import date, time
from decimal import Decimal

from meterbill import RESIDENTIAL_EV_2026, RESIDENTIAL_TOU_2026, Band, TouTariff, compute_bill

from .helpers import local_day_intervals, period_intervals

ZONE = "America/Chicago"
Q = Decimal("0.25")


def weekdays(first, last):
    n, d = 0, first
    while d <= last:
        n += d.weekday() < 5
        d = date.fromordinal(d.toordinal() + 1)
    return n


class SpringForwardTest(unittest.TestCase):
    def test_march_month(self):
        first, last = date(2026, 3, 1), date(2026, 3, 31)
        ivs = period_intervals(ZONE, first, last)
        self.assertEqual(len(ivs), 96 * 31 - 4)
        bill = compute_bill(RESIDENTIAL_TOU_2026, ivs, first, last)
        wd = weekdays(first, last)
        self.assertEqual(bill.line("PEAK").quantity, Decimal("4") * wd)
        self.assertEqual(bill.line("SHOULDER").quantity, Decimal("11") * wd)
        self.assertEqual(sum(l.quantity for l in bill.lines[:3]), Q * len(ivs))
        self.assertEqual(bill.line("DAILY").quantity, 31)

    def test_short_day(self):
        d = date(2026, 3, 8)
        bill = compute_bill(RESIDENTIAL_TOU_2026, local_day_intervals(ZONE, d), d, d)
        self.assertEqual(bill.line("OFFPEAK").quantity, Decimal("23"))
        self.assertEqual(bill.line("DAILY").quantity, 1)
        self.assertEqual(bill.line("DAILY").amount, Decimal("0.49"))

    def test_peak_hour_after_change(self):
        d = date(2026, 3, 9)  # Monday after the change, CDT (UTC-5)
        ivs = local_day_intervals(ZONE, d, lambda t: Decimal("1") if t.hour == 16 else Decimal("0"))
        bill = compute_bill(RESIDENTIAL_TOU_2026, ivs, date(2026, 3, 1), date(2026, 3, 31))
        self.assertEqual(bill.line("PEAK").quantity, Decimal("4"))
        self.assertEqual(bill.line("SHOULDER").quantity, 0)


class FallBackTest(unittest.TestCase):
    def test_long_day(self):
        d = date(2026, 11, 1)
        ivs = local_day_intervals(ZONE, d)
        self.assertEqual(len(ivs), 100)
        bill = compute_bill(RESIDENTIAL_TOU_2026, ivs, d, d)
        self.assertEqual(bill.line("OFFPEAK").quantity, Decimal("25"))
        self.assertEqual(bill.line("DAILY").quantity, 1)

    def test_november_month(self):
        first, last = date(2026, 11, 1), date(2026, 11, 30)
        ivs = period_intervals(ZONE, first, last)
        bill = compute_bill(RESIDENTIAL_TOU_2026, ivs, first, last)
        wd = weekdays(first, last)
        self.assertEqual(bill.line("PEAK").quantity, Decimal("4") * wd)
        self.assertEqual(sum(l.quantity for l in bill.lines[:3]), Q * len(ivs))
        self.assertEqual(bill.line("DAILY").quantity, 30)
        self.assertEqual(bill.line("DAILY").amount, Decimal("14.79"))

    def test_evening_profile_on_last_october_weekday(self):
        d = date(2026, 10, 30)  # Friday before the change (CDT); period spans the change
        ivs = local_day_intervals(ZONE, d, lambda t: Decimal("1") if t.hour == 19 else Decimal("0"))
        bill = compute_bill(RESIDENTIAL_TOU_2026, ivs, date(2026, 10, 30), date(2026, 11, 5))
        self.assertEqual(bill.line("PEAK").quantity, Decimal("4"))


class WrappingWindowTest(unittest.TestCase):
    def test_ev_overnight_band(self):
        d = date(2026, 1, 14)
        bill = compute_bill(RESIDENTIAL_EV_2026, local_day_intervals(ZONE, d), d, d)
        self.assertEqual(bill.line("EVNIGHT").quantity, Decimal("6"))
        self.assertEqual(bill.line("PEAK").quantity, Decimal("4"))
        self.assertEqual(bill.line("OFFPEAK").quantity, Decimal("14"))
        self.assertEqual([l.code for l in bill.lines], ["EVNIGHT", "PEAK", "OFFPEAK", "DAILY"])

    def test_ev_weekend(self):
        d = date(2026, 1, 17)
        bill = compute_bill(RESIDENTIAL_EV_2026, local_day_intervals(ZONE, d), d, d)
        self.assertEqual(bill.line("EVNIGHT").quantity, Decimal("6"))
        self.assertEqual(bill.line("OFFPEAK").quantity, Decimal("18"))


class RoundingTest(unittest.TestCase):
    FLAT = TouTariff("FLAT", ZONE, (), Band("ALL", "Energy", Decimal("0.25"), weekdays_only=False),
                     Decimal("0.125"))

    def test_line_rounds_half_up_on_exact_product(self):
        d = date(2026, 1, 14)
        ivs = local_day_intervals(ZONE, d, lambda t: Decimal("0"))
        ivs[0] = dataclasses.replace(ivs[0], kwh=Decimal("10.7"))
        bill = compute_bill(self.FLAT, ivs, d, d)
        self.assertEqual(bill.line("ALL").amount, Decimal("2.68"))      # 2.675 -> 2.68
        self.assertEqual(bill.line("DAILY").amount, Decimal("0.13"))    # 0.125 -> 0.13
        self.assertEqual(bill.total, Decimal("2.81"))

    def test_quantity_is_exact(self):
        d = date(2026, 1, 14)
        ivs = local_day_intervals(ZONE, d, lambda t: Decimal("0.0625"))
        bill = compute_bill(self.FLAT, ivs, d, d)
        self.assertEqual(bill.line("ALL").quantity, Decimal("6.0000"))
        ivs = local_day_intervals(ZONE, d, lambda t: Decimal("0.1371"))
        bill = compute_bill(self.FLAT, ivs, d, d)
        self.assertEqual(bill.line("ALL").quantity, Decimal("13.1616"))
        self.assertEqual(bill.line("ALL").amount, Decimal("3.29"))

    def test_amounts_are_decimal_cents(self):
        d = date(2026, 1, 14)
        bill = compute_bill(RESIDENTIAL_TOU_2026, local_day_intervals(ZONE, d), d, d)
        for line in bill.lines:
            self.assertIsInstance(line.amount, Decimal)
            self.assertEqual(line.amount, line.amount.quantize(Decimal("0.01")))


class WinterGuardTest(unittest.TestCase):
    def test_winter_week_unchanged(self):
        first, last = date(2026, 2, 2), date(2026, 2, 8)
        bill = compute_bill(RESIDENTIAL_TOU_2026, period_intervals(ZONE, first, last), first, last)
        self.assertEqual(bill.line("PEAK").quantity, Decimal("20"))
        self.assertEqual(bill.line("DAILY").amount, Decimal("3.45"))


if __name__ == "__main__":
    unittest.main()
