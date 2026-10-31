import unittest

from payments_core.bic import validate_bic
from payments_core.errors import ErrorCode


class BicTest(unittest.TestCase):
    def test_eight_and_eleven(self):
        self.assertTrue(validate_bic("DEUTDEFF").valid)
        res = validate_bic("deutdeff500")
        self.assertTrue(res.valid)
        self.assertEqual(res.branch, "500")

    def test_default_branch(self):
        self.assertEqual(validate_bic("BNPAFRPP").branch, "XXX")

    def test_test_bic_rejected(self):
        self.assertEqual(validate_bic("DEUTDE10").error, ErrorCode.INVALID_BIC)

    def test_structure(self):
        for bad in ("DEUT", "DEUTDEF", "1EUTDEFF", "DEUTDEFF5", "DEUTDEFF50"):
            with self.subTest(bad=bad):
                self.assertEqual(validate_bic(bad).error, ErrorCode.INVALID_BIC)

    def test_country_mismatch(self):
        res = validate_bic("BNPAFRPP", expected_country="DE")
        self.assertEqual(res.error, ErrorCode.BIC_COUNTRY_MISMATCH)


if __name__ == "__main__":
    unittest.main()
