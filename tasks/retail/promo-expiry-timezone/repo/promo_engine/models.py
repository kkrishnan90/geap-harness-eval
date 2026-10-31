from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List, Optional


@dataclass(frozen=True)
class Promotion:
    """A promotion valid from `starts_on` through `expires_on` (both inclusive,
    calendar dates in the store's time zone)."""

    code: str
    description: str
    starts_on: date
    expires_on: date
    percent_off: Decimal = Decimal("0")
    amount_off: Decimal = Decimal("0")
    min_basket: Decimal = Decimal("0")
    sku_prefix: Optional[str] = None  # None = whole basket

    def __post_init__(self):
        if self.expires_on < self.starts_on:
            raise ValueError(f"{self.code}: expires before it starts")


@dataclass(frozen=True)
class CartLine:
    sku: str
    unit_price: Decimal
    quantity: int = 1

    @property
    def total(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass
class Cart:
    store_id: str
    lines: List[CartLine] = field(default_factory=list)

    @property
    def subtotal(self) -> Decimal:
        return sum((l.total for l in self.lines), Decimal("0"))
