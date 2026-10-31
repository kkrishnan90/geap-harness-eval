import unittest
from decimal import Decimal

from parcelrate import Parcel, billable_weight, dimensional_weight, quote

D = Decimal


class DimensionalWeightTest(unittest.TestCase):
    def test_divisor_is_5000(self):
        self.assertEqual(dimensional_weight(Parcel(1, 50, 40, 30)), D("12"))

    def test_dimensional_weight_dominates(self):
        self.assertEqual(billable_weight(Parcel(2, 40, 30, 30)), D("7.5"))

    def test_actual_weight_dominates(self):
        self.assertEqual(billable_weight(Parcel("4.2", 10, 10, 10)), D("4.5"))


class BillableRoundingTest(unittest.TestCase):
    def test_rounds_up_to_next_half_kg(self):
        self.assertEqual(billable_weight(Parcel("1.1", 10, 10, 10)), D("1.5"))
        self.assertEqual(billable_weight(Parcel("1.6", 10, 10, 10)), D("2.0"))

    def test_exact_step_unchanged(self):
        self.assertEqual(billable_weight(Parcel("2.5", 10, 10, 10)), D("2.5"))

    def test_minimum_half_kg(self):
        self.assertEqual(billable_weight(Parcel("0.05", 5, 5, 5)), D("0.5"))


class LimitsTest(unittest.TestCase):
    def test_thirty_kg_allowed(self):
        self.assertEqual(billable_weight(Parcel(30, 10, 10, 10)), D("30"))

    def test_over_limit_by_actual(self):
        with self.assertRaises(ValueError):
            billable_weight(Parcel("30.2", 10, 10, 10))

    def test_over_limit_by_volume(self):
        with self.assertRaises(ValueError):
            quote(Parcel(5, 60, 60, 50), "44135")

    def test_non_positive_rejected(self):
        with self.assertRaises(ValueError):
            billable_weight(Parcel(0, 10, 10, 10))
        with self.assertRaises(ValueError):
            billable_weight(Parcel(1, 10, -1, 10))


class QuoteTest(unittest.TestCase):
    def test_zone_one_basic(self):
        q = quote(Parcel("1.1", 10, 10, 10), "44135")
        self.assertEqual((q.zone, q.billable_kg), (1, D("1.5")))
        self.assertEqual(q.transport, D("6.10"))
        self.assertEqual(q.fuel, D("0.73"))
        self.assertEqual(q.surcharges, {})
        self.assertEqual(q.total, D("6.83"))

    def test_oversize_boundary_120_not_oversize(self):
        q = quote(Parcel(1, 120, 10, 10), "44135")
        self.assertNotIn("oversize", q.surcharges)

    def test_oversize_and_fuel_on_transport_only(self):
        q = quote(Parcel(1, 121, 10, 10), "44135")
        self.assertEqual(q.surcharges, {"oversize": D("15.00")})
        self.assertEqual(q.transport, D("7.30"))
        self.assertEqual(q.fuel, D("0.88"))
        self.assertEqual(q.total, D("23.18"))

    def test_remote_area(self):
        q = quote(Parcel(1, 10, 10, 10), "25999")
        self.assertTrue(q.remote)
        self.assertEqual(q.surcharges, {"remote_area": D("4.50")})
        self.assertEqual(q.fuel, D("0.81"))
        self.assertEqual(q.total, D("12.06"))


if __name__ == "__main__":
    unittest.main()
