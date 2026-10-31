import os
import tempfile
import unittest
from datetime import date, timedelta
from decimal import Decimal

from meterbill import Interval
from meterbill.csvio import read_intervals
from meterbill.holidays import utility_holidays
from meterbill.intervals import utc
from meterbill.tax import with_tax
from meterbill.validation import check_intervals


class ValidationTest(unittest.TestCase):
    def test_gap_negative_duplicate(self):
        ivs = [Interval(utc(2026, 1, 1, 0, 0), Decimal("1")),
               Interval(utc(2026, 1, 1, 0, 15), Decimal("-0.1")),
               Interval(utc(2026, 1, 1, 0, 15), Decimal("0.2")),
               Interval(utc(2026, 1, 1, 1, 0), Decimal("0.2"))]
        kinds = sorted(i.kind for i in check_intervals(ivs))
        self.assertEqual(kinds, ["DUPLICATE", "GAP", "NEGATIVE"])

    def test_naive_rejected(self):
        from datetime import datetime
        with self.assertRaises(ValueError):
            Interval(datetime(2026, 1, 1), Decimal("1"))


class HolidayCalendarTest(unittest.TestCase):
    def test_2026(self):
        h = utility_holidays(2026)
        self.assertIn(date(2026, 11, 26), h)   # Thanksgiving
        self.assertIn(date(2026, 5, 25), h)    # Memorial Day
        self.assertIn(date(2026, 9, 7), h)     # Labor Day


class TaxAndCsvTest(unittest.TestCase):
    def test_tax(self):
        self.assertEqual(with_tax(Decimal("100.00")), (Decimal("6.25"), Decimal("106.25")))

    def test_csv(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.csv")
            with open(p, "w") as fh:
                fh.write("meter_id,interval_start_utc,kwh\nM1,2026-01-01T06:00:00Z,0.125\nM2,2026-01-01T06:00:00Z,9\n")
            ivs = read_intervals(p, "M1")
            self.assertEqual(ivs, [Interval(utc(2026, 1, 1, 6), Decimal("0.125"))])


if __name__ == "__main__":
    unittest.main()
