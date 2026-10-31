import unittest

from payments_core.errors import ErrorCode
from payments_core.sepa import CreditTransfer, precheck


def _ct(**kw):
    base = dict(
        debtor_name="ACME Logistics GmbH",
        debtor_iban="DE89370400440532013000",
        creditor_name="Fournitures Martin SARL",
        creditor_iban="FR1420041010050500013M02606",
        amount="1250.00",
    )
    base.update(kw)
    return CreditTransfer(**base)


class PrecheckTest(unittest.TestCase):
    def test_clean_transfer(self):
        self.assertTrue(precheck(_ct()).ok)

    def test_non_sepa_creditor(self):
        report = precheck(_ct(creditor_iban="AE070331234567890123456"))
        self.assertIn(("creditor_iban", ErrorCode.NON_SEPA_COUNTRY), report.errors)

    def test_amount_rules(self):
        for amount in ("0", "-5", "1.001", "abc", "1000000000.00"):
            with self.subTest(amount=amount):
                report = precheck(_ct(amount=amount))
                self.assertIn(("amount", ErrorCode.INVALID_AMOUNT), report.errors)

    def test_currency(self):
        report = precheck(_ct(currency="USD"))
        self.assertIn(("currency", ErrorCode.UNSUPPORTED_CURRENCY), report.errors)

    def test_missing_names(self):
        report = precheck(_ct(debtor_name=" "))
        self.assertIn(("debtor_name", ErrorCode.MISSING_FIELD), report.errors)


if __name__ == "__main__":
    unittest.main()
