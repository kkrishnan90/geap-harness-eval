import unittest

from payments_core import ErrorCode, format_iban, validate_iban

VALID = [
    "GB82WEST12345698765432",
    "DE89370400440532013000",
    "FR1420041010050500013M02606",
    "NL91ABNA0417164300",
    "BE68539007547034",
    "CH9300762011623852957",
    "AT611904300234573201",
]


class ValidateIbanTest(unittest.TestCase):
    def test_valid_electronic_format(self):
        for iban in VALID:
            with self.subTest(iban=iban):
                res = validate_iban(iban)
                self.assertTrue(res.valid, res)
                self.assertEqual(res.error, ErrorCode.OK)
                self.assertEqual(res.normalized, iban)
                self.assertEqual(res.country, iban[:2])

    def test_bad_checksum(self):
        res = validate_iban("GB82WEST12345698765433")
        self.assertFalse(res.valid)
        self.assertEqual(res.error, ErrorCode.INVALID_CHECKSUM)

    def test_too_short(self):
        res = validate_iban("DE8937040044053201300")
        self.assertEqual(res.error, ErrorCode.INVALID_LENGTH)

    def test_empty(self):
        self.assertEqual(validate_iban("").error, ErrorCode.EMPTY)
        self.assertEqual(validate_iban("   ").error, ErrorCode.EMPTY)
        self.assertEqual(validate_iban(None).error, ErrorCode.EMPTY)

    def test_punctuation_rejected(self):
        res = validate_iban("GB82-WEST-1234-5698-7654-32")
        self.assertEqual(res.error, ErrorCode.INVALID_CHARACTERS)

    def test_result_is_falsy_when_invalid(self):
        self.assertFalse(validate_iban("XX"))
        self.assertTrue(validate_iban(VALID[0]))


class FormatIbanTest(unittest.TestCase):
    def test_groups_of_four(self):
        self.assertEqual(format_iban("FR1420041010050500013M02606"),
                         "FR14 2004 1010 0505 0001 3M02 606")

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            format_iban("GB82WEST12345698765433")


if __name__ == "__main__":
    unittest.main()
