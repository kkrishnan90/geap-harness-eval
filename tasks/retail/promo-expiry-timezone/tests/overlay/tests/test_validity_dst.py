import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from promo_engine.models import Cart, CartLine, Promotion
from promo_engine.pricing import price_cart
from promo_engine.validity import days_remaining, is_active, promo_window

UTC = timezone.utc
NYC = ZoneInfo("America/New_York")
BERLIN = ZoneInfo("Europe/Berlin")
SYDNEY = ZoneInfo("Australia/Sydney")
TOKYO = ZoneInfo("Asia/Tokyo")


def promo(start, end, code="PROMO"):
    return Promotion(code, "test", start, end, percent_off=Decimal("10"))


class SpringForwardTest(unittest.TestCase):
    # US DST starts 2026-03-08 02:00 local.
    def test_window_end_uses_offset_on_expiry_day(self):
        p = promo(date(2026, 3, 1), date(2026, 3, 15))
        start, end = promo_window(p, NYC)
        self.assertEqual(start, datetime(2026, 3, 1, 5, 0, tzinfo=UTC))
        self.assertEqual(end, datetime(2026, 3, 16, 4, 0, tzinfo=UTC))

    def test_inactive_half_hour_after_local_midnight(self):
        p = promo(date(2026, 3, 1), date(2026, 3, 15))
        self.assertFalse(is_active(p, datetime(2026, 3, 16, 0, 30, tzinfo=NYC), NYC))

    def test_start_on_transition_day(self):
        p = promo(date(2026, 3, 8), date(2026, 3, 10))
        # 23:30 EST on 7 March is 04:30 UTC on 8 March: not yet started locally.
        self.assertFalse(is_active(p, datetime(2026, 3, 8, 4, 30, tzinfo=UTC), NYC))
        self.assertTrue(is_active(p, datetime(2026, 3, 8, 0, 0, tzinfo=NYC), NYC))


class FallBackTest(unittest.TestCase):
    # EU DST ends 2026-10-25 03:00 local.
    def test_active_until_local_midnight(self):
        p = promo(date(2026, 10, 20), date(2026, 10, 31))
        self.assertTrue(is_active(p, datetime(2026, 10, 31, 23, 30, tzinfo=BERLIN), BERLIN))

    def test_window(self):
        p = promo(date(2026, 10, 20), date(2026, 10, 31))
        self.assertEqual(promo_window(p, BERLIN),
                         (datetime(2026, 10, 19, 22, 0, tzinfo=UTC), datetime(2026, 10, 31, 23, 0, tzinfo=UTC)))

    def test_pricing_applies_on_last_evening(self):
        p = Promotion("AUTUMN20", "20%", date(2026, 10, 20), date(2026, 10, 31), percent_off=Decimal("20"))
        c = Cart("DE-BER-001", [CartLine("COAT-WOOL-M", Decimal("150.00"))])
        priced = price_cart(c, [p], datetime(2026, 10, 31, 22, 45, tzinfo=UTC))  # 23:45 CET
        self.assertEqual([d.amount for d in priced.discounts], [Decimal("30.00")])


class SouthernHemisphereTest(unittest.TestCase):
    # Sydney DST ends 2026-04-05 03:00 local.
    def test_last_evening_active(self):
        p = promo(date(2026, 4, 1), date(2026, 4, 10))
        self.assertTrue(is_active(p, datetime(2026, 4, 10, 23, 30, tzinfo=SYDNEY), SYDNEY))


class LastSecondTest(unittest.TestCase):
    def test_final_second_of_expiry_day(self):
        p = promo(date(2026, 3, 1), date(2026, 3, 7))
        self.assertTrue(is_active(p, datetime(2026, 3, 7, 23, 59, 59, 500000, tzinfo=TOKYO), TOKYO))

    def test_end_is_exclusive_local_midnight(self):
        p = promo(date(2026, 3, 1), date(2026, 3, 7))
        _, end = promo_window(p, TOKYO)
        self.assertEqual(end, datetime(2026, 3, 8, 0, 0, tzinfo=TOKYO))
        self.assertFalse(is_active(p, end, TOKYO))
        self.assertTrue(is_active(p, end - timedelta(microseconds=1), TOKYO))


class DaysRemainingLocalDateTest(unittest.TestCase):
    def test_evening_in_new_york(self):
        p = promo(date(2026, 3, 1), date(2026, 3, 20))
        # 21:00 EDT on 18 March is already 19 March in UTC.
        self.assertEqual(days_remaining(p, datetime(2026, 3, 19, 1, 0, tzinfo=UTC), NYC), 2)

    def test_morning_in_sydney(self):
        p = promo(date(2026, 4, 1), date(2026, 4, 10))
        # 08:00 AEST on 9 April is still 8 April in UTC.
        self.assertEqual(days_remaining(p, datetime(2026, 4, 8, 22, 0, tzinfo=UTC), SYDNEY), 1)


class NaiveDatetimeTest(unittest.TestCase):
    def test_is_active_rejects_naive(self):
        p = promo(date(2026, 3, 1), date(2026, 3, 7))
        with self.assertRaises(ValueError):
            is_active(p, datetime(2026, 3, 4, 12, 0), TOKYO)

    def test_days_remaining_rejects_naive(self):
        p = promo(date(2026, 3, 1), date(2026, 3, 7))
        with self.assertRaises(ValueError):
            days_remaining(p, datetime(2026, 3, 4, 12, 0), TOKYO)


class BoundaryGuardTest(unittest.TestCase):
    """Regression guards: behaviour that is already right must stay right."""

    def test_inactive_at_local_midnight_after_fall_back(self):
        p = promo(date(2026, 10, 20), date(2026, 10, 31))
        self.assertFalse(is_active(p, datetime(2026, 11, 1, 0, 0, tzinfo=BERLIN), BERLIN))

    def test_india_half_hour_offset(self):
        tz = ZoneInfo("Asia/Kolkata")
        p = promo(date(2026, 8, 15), date(2026, 8, 15))
        self.assertTrue(is_active(p, datetime(2026, 8, 14, 18, 30, tzinfo=UTC), tz))
        self.assertFalse(is_active(p, datetime(2026, 8, 14, 18, 29, 59, tzinfo=UTC), tz))


if __name__ == "__main__":
    unittest.main()
