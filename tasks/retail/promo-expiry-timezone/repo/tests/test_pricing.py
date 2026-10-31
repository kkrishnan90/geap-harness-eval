import unittest
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from promo_engine.models import Cart, CartLine, Promotion
from promo_engine.pricing import price_cart

BERLIN = ZoneInfo("Europe/Berlin")


def cart():
    return Cart("DE-BER-001", [
        CartLine("SHOE-RUN-42", Decimal("89.99")),
        CartLine("SOCK-3PK", Decimal("12.50"), 2),
    ])


class PriceCartTest(unittest.TestCase):
    def test_percent_whole_basket(self):
        p = Promotion("WINTER15", "15%", date(2026, 1, 10), date(2026, 1, 20), percent_off=Decimal("15"))
        priced = price_cart(cart(), [p], datetime(2026, 1, 15, 14, 0, tzinfo=BERLIN))
        self.assertEqual(priced.subtotal, Decimal("114.99"))
        self.assertEqual(priced.discounts[0].amount, Decimal("17.25"))
        self.assertEqual(priced.total, Decimal("97.74"))

    def test_sku_prefix_and_amount(self):
        p = Promotion("SOCKS5", "5 off socks", date(2026, 1, 1), date(2026, 1, 31),
                      amount_off=Decimal("5"), sku_prefix="SOCK")
        priced = price_cart(cart(), [p], datetime(2026, 1, 15, 14, 0, tzinfo=BERLIN))
        self.assertEqual(priced.discounts[0].amount, Decimal("5.00"))

    def test_inactive_not_applied(self):
        p = Promotion("WINTER15", "15%", date(2026, 1, 10), date(2026, 1, 20), percent_off=Decimal("15"))
        priced = price_cart(cart(), [p], datetime(2026, 2, 1, 10, 0, tzinfo=BERLIN))
        self.assertEqual(priced.discounts, [])

    def test_min_basket(self):
        p = Promotion("BIG20", "20 off 150", date(2026, 1, 1), date(2026, 1, 31),
                      amount_off=Decimal("20"), min_basket=Decimal("150"))
        priced = price_cart(cart(), [p], datetime(2026, 1, 15, 14, 0, tzinfo=BERLIN))
        self.assertEqual(priced.discounts, [])

    def test_discount_never_exceeds_basket(self):
        p = Promotion("FREE", "200 off", date(2026, 1, 1), date(2026, 1, 31), amount_off=Decimal("200"))
        priced = price_cart(cart(), [p], datetime(2026, 1, 15, 14, 0, tzinfo=BERLIN))
        self.assertEqual(priced.total, Decimal("0.00"))


if __name__ == "__main__":
    unittest.main()
