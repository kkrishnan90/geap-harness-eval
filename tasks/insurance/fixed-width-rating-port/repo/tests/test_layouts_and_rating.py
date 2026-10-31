import unittest
from decimal import Decimal

from prmrate import layouts, rating
from prmrate.calendar import next_business_day, parse_run_date
from prmrate.report import summarise


def detail(product="MTR", si="00001250000", risk="B", age="041", claims="00", adj="000000{"):
    return ("DMTR0000101" + product + si + risk + age + claims + adj).ljust(80)


class LayoutTest(unittest.TestCase):
    def test_input_detail_columns(self):
        raw = layouts.IN_DETAIL.parse(detail())
        self.assertEqual(raw["policy_no"], "MTR0000101")
        self.assertEqual(raw["product"], "MTR")
        self.assertEqual(raw["sum_insured"], "00001250000")
        self.assertEqual(raw["risk_class"], "B")
        self.assertEqual(raw["adjustment"], "000000{")

    def test_header_record(self):
        line = layouts.OUT_HEADER.build({"rec_type": "H", "run_date": 20260315, "batch_id": "RN0315"})
        self.assertEqual(line, "H20260315RN0315".ljust(64))


class BasicRatingTest(unittest.TestCase):
    def test_standard_motor(self):
        r = rating.rate_detail(detail())
        self.assertTrue(r.ok)
        self.assertEqual(r.base_premium, Decimal("284.38"))
        self.assertEqual(r.loading, Decimal("0.00"))
        self.assertEqual(r.final_premium, Decimal("284.38"))

    def test_young_driver_and_claim(self):
        r = rating.rate_detail(detail(si="00000800000", risk="C", age="022", claims="01"))
        self.assertEqual(r.base_premium, Decimal("219.20"))
        self.assertEqual(r.loading, Decimal("98.64"))

    def test_rejects(self):
        self.assertEqual(rating.rate_detail(detail(product="BOT")).reason, "E001")
        self.assertEqual(rating.rate_detail(detail(risk="F")).reason, "E002")
        self.assertEqual(rating.rate_detail(detail(si="00000000000")).reason, "E003")
        self.assertEqual(rating.rate_detail(detail(age="0 1")).reason, "E009")
        self.assertEqual(rating.rate_detail(detail(product="BOT")).status, "RJ")


class OpsHelpersTest(unittest.TestCase):
    def test_calendar(self):
        d = parse_run_date("20260313")  # Friday
        self.assertEqual(next_business_day(d).isoformat(), "2026-03-16")

    def test_summary(self):
        text = summarise(["H...", ("R" + " " * 45 + "RJE001").ljust(64)])
        self.assertIn("reject E001: 1", text)


if __name__ == "__main__":
    unittest.main()
