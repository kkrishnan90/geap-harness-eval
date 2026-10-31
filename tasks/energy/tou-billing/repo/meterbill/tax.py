from decimal import ROUND_HALF_UP, Decimal

STATE_RATE = Decimal("0.0625")


def with_tax(total, rate=STATE_RATE):
    tax = (total * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return tax, total + tax
