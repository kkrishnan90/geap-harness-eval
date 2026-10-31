"""Hidden behavioural checks of the reference rating implementation."""
import unittest
from decimal import Decimal

from parcelrate import Parcel, quote


class ReferenceQuoteTest(unittest.TestCase):
    def test_zone_five_heavy(self):
        q = quote(Parcel("9.7", 30, 30, 30), "80331")
        self.assertEqual(q.billable_kg, Decimal("10.0"))
        self.assertEqual(q.transport, Decimal("30.20"))
        self.assertEqual(q.total, Decimal("33.82"))

    def test_remote_oversize(self):
        q = quote(Parcel(2, 130, 20, 10), "18565")
        self.assertEqual(set(q.surcharges), {"oversize", "remote_area"})


if __name__ == "__main__":
    unittest.main()
