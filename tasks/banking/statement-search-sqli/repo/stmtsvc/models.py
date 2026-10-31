from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .errors import SearchError


@dataclass(frozen=True)
class Transaction:
    id: int
    account_id: str
    booking_date: str
    value_date: str
    amount_minor: int
    currency: str
    counterparty: str
    description: str
    category: str
    reference: str

    @property
    def amount(self) -> Decimal:
        return (Decimal(self.amount_minor) / 100).quantize(Decimal("0.01"))

    def as_dict(self):
        return {
            "id": self.id,
            "booking_date": self.booking_date,
            "value_date": self.value_date,
            "amount": str(self.amount),
            "currency": self.currency,
            "counterparty": self.counterparty,
            "description": self.description,
            "category": self.category,
            "reference": self.reference,
        }


COLUMNS = ("id", "account_id", "booking_date", "value_date", "amount_minor", "currency",
           "counterparty", "description", "category", "reference")


def row_to_transaction(row) -> Transaction:
    return Transaction(*row)


def to_minor(value) -> int:
    """Decimal/str/int amount in major units -> integer minor units. Raises SearchError."""
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise SearchError(f"invalid amount: {value!r}") from None
    if not d.is_finite():
        raise SearchError(f"invalid amount: {value!r}")
    return int((d * 100).to_integral_value())
