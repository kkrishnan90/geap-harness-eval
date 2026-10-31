import unittest

from payments_core import ErrorCode, format_iban, normalize_iban, validate_iban
from payments_core.sepa import CreditTransfer, precheck


class LowercaseInputTest(unittest.TestCase):
    def test_lowercase_compact(self):
        res = validate_iban("gb82west12345698765432")
        self.assertTrue(res.valid, res)
        self.assertEqual(res.normalized, "GB82WEST12345698765432")
        self.assertEqual(res.country, "GB")

    def test_mixed_case(self):
        res = validate_iban("Fr1420041010050500013m02606")
        self.assertTrue(res.valid, res)
        self.assertEqual(res.normalized, "FR1420041010050500013M02606")

    def test_lowercase_bad_checksum_still_checksum_error(self):
        res = validate_iban("gb82west12345698765433")
        self.assertEqual(res.error, ErrorCode.INVALID_CHECKSUM)


class SpacedInputTest(unittest.TestCase):
    def test_paper_format(self):
        res = validate_iban("DE89 3704 0044 0532 0130 00")
        self.assertTrue(res.valid, res)
        self.assertEqual(res.normalized, "DE89370400440532013000")

    def test_irregular_spacing_and_padding(self):
        res = validate_iban("  nl91 abna  0417 1643 00 ")
        self.assertTrue(res.valid, res)
        self.assertEqual(res.normalized, "NL91ABNA0417164300")

    def test_longest_country_spaced_lowercase(self):
        res = validate_iban("lc55 hemm 0001 0001 0012 0012 0002 3015")
        self.assertTrue(res.valid, res)
        self.assertEqual(res.country, "LC")

    def test_tab_inside_rejected(self):
        res = validate_iban("GB82\tWEST12345698765432")
        self.assertEqual(res.error, ErrorCode.INVALID_CHARACTERS)

    def test_normalize_iban(self):
        self.assertEqual(normalize_iban(" mt84 malt 0110 0001 2345 mtlc ast0 01s "),
                         "MT84MALT011000012345MTLCAST001S")

    def test_format_from_typed_input(self):
        self.assertEqual(format_iban("be68 5390 0754 7034"), "BE68 5390 0754 7034")


class CountryLengthTest(unittest.TestCase):
    def test_too_long_with_valid_checksum(self):
        # 16 characters, check digits valid for this BBAN, but Norway is 15.
        res = validate_iban("NO37860111179470")
        self.assertFalse(res.valid)
        self.assertEqual(res.error, ErrorCode.INVALID_LENGTH)
        self.assertEqual(res.country, "NO")

    def test_too_long_germany(self):
        res = validate_iban("DE54 3704 0044 0532 0130 001")
        self.assertEqual(res.error, ErrorCode.INVALID_LENGTH)

    def test_too_short_lowercase(self):
        res = validate_iban("gb88west1234569876543")
        self.assertEqual(res.error, ErrorCode.INVALID_LENGTH)

    def test_unknown_country(self):
        res = validate_iban("ZZ1812345678901234")
        self.assertFalse(res.valid)
        self.assertEqual(res.error, ErrorCode.UNKNOWN_COUNTRY)
        self.assertEqual(res.country, "ZZ")

    def test_kosovo_registered(self):
        self.assertTrue(validate_iban("xk05 1212 0123 4567 8906").valid)


class SepaPrecheckTypedInputTest(unittest.TestCase):
    def test_precheck_accepts_typed_ibans(self):
        ct = CreditTransfer(
            debtor_name="ACME Logistics GmbH",
            debtor_iban="de89 3704 0044 0532 0130 00",
            creditor_name="Fournitures Martin SARL",
            creditor_iban="FR14 2004 1010 0505 0001 3M02 606",
            amount="99.90",
        )
        self.assertTrue(precheck(ct).ok, precheck(ct).errors)


if __name__ == "__main__":
    unittest.main()
