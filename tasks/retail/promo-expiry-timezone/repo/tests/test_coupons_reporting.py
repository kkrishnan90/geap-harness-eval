import unittest
from datetime import date
from decimal import Decimal

from promo_engine.coupons import is_well_formed, make_code
from promo_engine.reporting import Redemption, summarize, to_csv_rows
from promo_engine.stores import all_stores, get_store


class CouponTest(unittest.TestCase):
    def test_roundtrip(self):
        for serial in (0, 1, 31, 32, 99999, 10**8):
            with self.subTest(serial=serial):
                self.assertTrue(is_well_formed(make_code("SPRG", serial)))

    def test_typo_detected(self):
        code = make_code("SPRG", 4711)
        bad = code[:6] + ("A" if code[6] != "A" else "B") + code[7:]
        self.assertFalse(is_well_formed(bad))

    def test_bad_campaign(self):
        with self.assertRaises(ValueError):
            make_code("SP0G", 1)


class ReportingTest(unittest.TestCase):
    def test_summary(self):
        rows = to_csv_rows(summarize([
            Redemption("DE-BER-001", "WINTER15", date(2026, 1, 15), Decimal("17.25")),
            Redemption("GB-LON-007", "WINTER15", date(2026, 1, 15), Decimal("3.10")),
            Redemption("GB-LON-007", "WINTER15", date(2026, 1, 16), Decimal("1.00")),
        ]))
        self.assertEqual(rows[1], ("2026-01-15", "WINTER15", "2", "20.35", "2"))
        self.assertEqual(len(rows), 3)


class StoresTest(unittest.TestCase):
    def test_lookup(self):
        self.assertEqual(str(get_store("JP-TYO-003").tz), "Asia/Tokyo")
        with self.assertRaises(KeyError):
            get_store("XX-NOPE-000")
        self.assertEqual(len(all_stores()), 7)


if __name__ == "__main__":
    unittest.main()
