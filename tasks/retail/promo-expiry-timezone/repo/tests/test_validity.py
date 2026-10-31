import unittest
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from promo_engine.models import Promotion
from promo_engine.validity import days_remaining, is_active

TOKYO = ZoneInfo("Asia/Tokyo")
NYC = ZoneInfo("America/New_York")


def promo(start, end):
    return Promotion("SPRING10", "10% off", start, end, percent_off=Decimal("10"))


class IsActiveTest(unittest.TestCase):
    def test_mid_window(self):
        p = promo(date(2026, 3, 1), date(2026, 3, 7))
        self.assertTrue(is_active(p, datetime(2026, 3, 4, 12, 0, tzinfo=TOKYO), TOKYO))

    def test_before_start(self):
        p = promo(date(2026, 3, 1), date(2026, 3, 7))
        self.assertFalse(is_active(p, datetime(2026, 2, 28, 23, 59, tzinfo=TOKYO), TOKYO))

    def test_first_minute(self):
        p = promo(date(2026, 3, 1), date(2026, 3, 7))
        self.assertTrue(is_active(p, datetime(2026, 3, 1, 0, 0, tzinfo=TOKYO), TOKYO))

    def test_after_expiry(self):
        p = promo(date(2026, 3, 1), date(2026, 3, 7))
        self.assertFalse(is_active(p, datetime(2026, 3, 8, 0, 0, 1, tzinfo=TOKYO), TOKYO))

    def test_instant_in_other_zone(self):
        # 23:00 in New York on the last day, observed from a UTC server.
        p = promo(date(2026, 6, 1), date(2026, 6, 7))
        at = datetime(2026, 6, 7, 23, 0, tzinfo=NYC).astimezone(ZoneInfo("UTC"))
        self.assertTrue(is_active(p, at, NYC))
        later = datetime(2026, 6, 8, 0, 0, 30, tzinfo=NYC)
        self.assertFalse(is_active(p, later, NYC))

    def test_single_day_promotion(self):
        p = promo(date(2026, 7, 4), date(2026, 7, 4))
        self.assertTrue(is_active(p, datetime(2026, 7, 4, 9, 0, tzinfo=NYC), NYC))
        self.assertFalse(is_active(p, datetime(2026, 7, 5, 9, 0, tzinfo=NYC), NYC))


class DaysRemainingTest(unittest.TestCase):
    def test_counts_calendar_days(self):
        p = promo(date(2026, 3, 1), date(2026, 3, 7))
        self.assertEqual(days_remaining(p, datetime(2026, 3, 4, 12, 0, tzinfo=TOKYO), TOKYO), 3)

    def test_zero_after_expiry(self):
        p = promo(date(2026, 3, 1), date(2026, 3, 7))
        self.assertEqual(days_remaining(p, datetime(2026, 3, 20, 12, 0, tzinfo=TOKYO), TOKYO), 0)


class PromotionModelTest(unittest.TestCase):
    def test_rejects_inverted_dates(self):
        with self.assertRaises(ValueError):
            promo(date(2026, 3, 7), date(2026, 3, 1))


if __name__ == "__main__":
    unittest.main()
