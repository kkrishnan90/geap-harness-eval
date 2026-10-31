"""Pre-validation of SEPA credit transfer (SCT) instructions before submission."""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import List

from .bic import validate_bic
from .errors import ErrorCode
from .iban import validate_iban
from .registry import SEPA_CURRENCIES, is_sepa_country

MAX_SCT_AMOUNT = Decimal("999999999.99")


@dataclass
class CreditTransfer:
    debtor_name: str
    debtor_iban: str
    creditor_name: str
    creditor_iban: str
    amount: str
    currency: str = "EUR"
    creditor_bic: str = ""
    remittance_info: str = ""


@dataclass
class PrecheckReport:
    errors: List[tuple] = field(default_factory=list)

    @property
    def ok(self):
        return not self.errors

    def add(self, field_name, code):
        self.errors.append((field_name, code))


def precheck(ct: CreditTransfer) -> PrecheckReport:
    report = PrecheckReport()
    for name in ("debtor_name", "creditor_name"):
        if not getattr(ct, name).strip():
            report.add(name, ErrorCode.MISSING_FIELD)

    for name in ("debtor_iban", "creditor_iban"):
        res = validate_iban(getattr(ct, name))
        if not res.valid:
            report.add(name, res.error)
        elif not is_sepa_country(res.country):
            report.add(name, ErrorCode.NON_SEPA_COUNTRY)

    if ct.creditor_bic:
        bic = validate_bic(ct.creditor_bic)
        if not bic.valid:
            report.add("creditor_bic", bic.error)

    if ct.currency not in SEPA_CURRENCIES:
        report.add("currency", ErrorCode.UNSUPPORTED_CURRENCY)

    try:
        amount = Decimal(ct.amount)
    except (InvalidOperation, TypeError):
        report.add("amount", ErrorCode.INVALID_AMOUNT)
    else:
        if amount <= 0 or amount > MAX_SCT_AMOUNT or amount.as_tuple().exponent < -2:
            report.add("amount", ErrorCode.INVALID_AMOUNT)

    if len(ct.remittance_info) > 140:
        report.add("remittance_info", ErrorCode.INVALID_CHARACTERS)
    return report
