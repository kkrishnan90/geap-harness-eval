"""Premium computation: port of paragraphs 3000-RATE-POLICY .. 3400-APPLY-MINIMUM."""

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from . import codecs, tables
from .layouts import IN_DETAIL

ZERO = Decimal("0.00")


def cobol_round(value, scale=2):
    """COMPUTE ... ROUNDED."""
    return Decimal(value).quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True)
class RatedPolicy:
    policy_no: str
    product: str
    base_premium: Decimal = ZERO
    loading: Decimal = ZERO
    adjustment: Decimal = ZERO
    final_premium: Decimal = ZERO
    status: str = "OK"
    reason: str = ""
    sum_insured: Decimal = None   # None when the field was not numeric

    @property
    def ok(self):
        return self.status == "OK"


def loading_percent(product, age, prior_claims):
    pct = 0
    if product == "MTR":
        if age < tables.YOUNG_DRIVER_AGE:
            pct += tables.YOUNG_DRIVER_LOADING
        elif age > tables.SENIOR_DRIVER_AGE:
            pct += tables.SENIOR_DRIVER_LOADING
    pct += tables.CLAIM_LOADING * prior_claims
    return pct


def rate_detail(line):
    raw = IN_DETAIL.parse(line)
    policy_no = codecs.decode_alnum(raw["policy_no"])
    product = codecs.decode_alnum(raw["product"])
    try:
        sum_insured = codecs.decode_unsigned(raw["sum_insured"], 2)
    except codecs.FieldError:
        sum_insured = None

    def reject(code):
        return RatedPolicy(policy_no, product, status="RJ", reason=code, sum_insured=sum_insured)

    try:
        age = int(codecs.decode_unsigned(raw["age"]))
        claims = int(codecs.decode_unsigned(raw["prior_claims"]))
        adjustment = codecs.decode_signed(raw["adjustment"], 2)
    except codecs.FieldError:
        return reject("E009")
    if sum_insured is None:
        return reject("E009")
    if product not in tables.RATE_PER_MILLE:
        return reject("E001")
    risk = raw["risk_class"]
    if risk not in tables.RATE_PER_MILLE[product]:
        return reject("E002")
    if sum_insured == 0:
        return reject("E003")

    base = cobol_round(sum_insured * tables.RATE_PER_MILLE[product][risk] / 1000)
    loading = cobol_round(base * loading_percent(product, age, claims) / 100)
    final = base + loading + adjustment
    minimum = tables.MINIMUM_PREMIUM[product]
    if final < minimum:
        final = minimum
    return RatedPolicy(policy_no, product, base, loading, adjustment, final, "OK", "", sum_insured)
