import unittest
from decimal import Decimal

from prmrate import codecs


class NegativeOverpunchTest(unittest.TestCase):
    def test_decode_every_negative_digit(self):
        for i, ch in enumerate("}JKLMNOPQR"):
            with self.subTest(ch=ch):
                self.assertEqual(codecs.decode_signed("000123" + ch, 2), -Decimal(1230 + i).scaleb(-2))

    def test_decode_every_positive_digit(self):
        for i, ch in enumerate("{ABCDEFGHI"):
            with self.subTest(ch=ch):
                self.assertEqual(codecs.decode_signed("000123" + ch, 2), Decimal(1230 + i).scaleb(-2))

    def test_invalid_sign_or_body(self):
        for bad in ("000020X", "00002 5", "0A0020}", " 00020{"):
            with self.subTest(bad=bad):
                with self.assertRaises(codecs.FieldError):
                    codecs.decode_signed(bad, 2)

    def test_encode_negative(self):
        self.assertEqual(codecs.encode_signed(Decimal("-25.50"), 7, 2), "000255}")
        self.assertEqual(codecs.encode_signed(Decimal("-100.07"), 7, 2), "001000P")
        self.assertEqual(codecs.encode_signed(Decimal("-1234.56"), 7, 2), "012345O")

    def test_zero_is_positive(self):
        self.assertEqual(codecs.encode_signed(Decimal("-0.00"), 7, 2), "000000{")

    def test_round_trip(self):
        for v in ("-99999.99", "-0.01", "0.01", "12345.67", "-5.00"):
            with self.subTest(v=v):
                self.assertEqual(codecs.decode_signed(codecs.encode_signed(Decimal(v), 7, 2), 2), Decimal(v))


class HighOrderTruncationTest(unittest.TestCase):
    def test_unsigned_move_drops_high_order_digits(self):
        self.assertEqual(codecs.encode_unsigned(Decimal("1234567"), 5), "34567")
        self.assertEqual(codecs.encode_unsigned(Decimal("123456.78"), 7, 2), "2345678")

    def test_signed_move_drops_high_order_digits(self):
        self.assertEqual(codecs.encode_signed(Decimal("-123456.78"), 7, 2), "234567Q")


if __name__ == "__main__":
    unittest.main()
