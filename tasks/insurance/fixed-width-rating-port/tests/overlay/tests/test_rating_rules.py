import unittest
from decimal import Decimal

from prmrate import rating


def detail(product="MTR", si="00001000000", risk="A", age="040", claims="00", adj="000000{"):
    return ("DPOL0000001" + product + si + risk + age + claims + adj).ljust(80)


class RoundedSemanticsTest(unittest.TestCase):
    def test_half_away_from_zero(self):
        self.assertEqual(rating.cobol_round(Decimal("2.345")), Decimal("2.35"))
        self.assertEqual(rating.cobol_round(Decimal("2.355")), Decimal("2.36"))
        self.assertEqual(rating.cobol_round(Decimal("-2.345")), Decimal("-2.35"))
        self.assertEqual(rating.cobol_round(Decimal("2.3449")), Decimal("2.34"))

    def test_base_premium_tie(self):
        # 10010.00 * 18.50 / 1000 = 185.185
        r = rating.rate_detail(detail(si="00001001000"))
        self.assertEqual(r.base_premium, Decimal("185.19"))


class LoadingRulesTest(unittest.TestCase):
    def test_senior_driver_from_seventy(self):
        self.assertEqual(rating.rate_detail(detail(age="069")).loading, Decimal("0.00"))
        self.assertEqual(rating.rate_detail(detail(age="070")).loading, Decimal("37.00"))

    def test_young_driver_boundary(self):
        self.assertEqual(rating.rate_detail(detail(age="024")).loading, Decimal("64.75"))
        self.assertEqual(rating.rate_detail(detail(age="025")).loading, Decimal("0.00"))

    def test_claims_loading_capped_at_five(self):
        five = rating.rate_detail(detail(claims="05"))
        nine = rating.rate_detail(detail(claims="09"))
        self.assertEqual(five.loading, Decimal("92.50"))
        self.assertEqual(nine.loading, Decimal("92.50"))

    def test_senior_loading_is_motor_only(self):
        self.assertEqual(rating.rate_detail(detail(product="HOM", si="00030000000", age="080")).loading, Decimal("0.00"))


class TravelAndMinimumTest(unittest.TestCase):
    def test_travel_is_rated(self):
        r = rating.rate_detail(detail(product="TRV", si="00000500000", risk="C", age="029"))
        self.assertTrue(r.ok, r)
        self.assertEqual(r.base_premium, Decimal("36.25"))

    def test_travel_minimum(self):
        r = rating.rate_detail(detail(product="TRV", si="00000080000", risk="A"))
        self.assertEqual(r.base_premium, Decimal("3.20"))
        self.assertEqual(r.final_premium, Decimal("25.00"))

    def test_negative_adjustment_applied_before_minimum(self):
        r = rating.rate_detail(detail(product="HOM", si="00025000000", risk="E", claims="01", adj="012345O"))
        self.assertTrue(r.ok, r)
        self.assertEqual(r.adjustment, Decimal("-1234.56"))
        self.assertEqual(r.final_premium, Decimal("90.00"))

    def test_small_negative_adjustment(self):
        r = rating.rate_detail(detail(si="00000700000", risk="B", adj="000020}"))
        self.assertEqual(r.final_premium, Decimal("157.25"))


if __name__ == "__main__":
    unittest.main()
