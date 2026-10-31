import unittest
from decimal import Decimal

from prmrate import codecs


class AlnumTest(unittest.TestCase):
    def test_decode_strips_trailing_spaces(self):
        self.assertEqual(codecs.decode_alnum("MTR0000101  "), "MTR0000101")

    def test_encode_pads_and_truncates(self):
        self.assertEqual(codecs.encode_alnum("AB", 4), "AB  ")
        self.assertEqual(codecs.encode_alnum("ABCDEF", 4), "ABCD")


class UnsignedTest(unittest.TestCase):
    def test_implied_decimals(self):
        self.assertEqual(codecs.decode_unsigned("00001250000", 2), Decimal("12500.00"))
        self.assertEqual(codecs.decode_unsigned("041"), Decimal(41))

    def test_not_numeric(self):
        for bad in ("0012 34", "   ", "00A1", ""):
            with self.subTest(bad=bad):
                with self.assertRaises(codecs.FieldError):
                    codecs.decode_unsigned(bad, 2)

    def test_encode(self):
        self.assertEqual(codecs.encode_unsigned(Decimal("476.01"), 15, 2), "000000000047601")
        self.assertEqual(codecs.encode_unsigned(7, 7), "0000007")


class PositiveSignedTest(unittest.TestCase):
    def test_positive_overpunch(self):
        self.assertEqual(codecs.decode_signed("000120{", 2), Decimal("12.00"))
        self.assertEqual(codecs.decode_signed("000011A", 2), Decimal("1.11"))
        self.assertEqual(codecs.decode_signed("0000150", 2), Decimal("1.50"))

    def test_encode_positive(self):
        self.assertEqual(codecs.encode_signed(Decimal("284.38"), 9, 2), "00002843H")
        self.assertEqual(codecs.encode_signed(Decimal("0"), 7, 2), "000000{")


if __name__ == "__main__":
    unittest.main()
