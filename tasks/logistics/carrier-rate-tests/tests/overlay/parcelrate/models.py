from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict


def to_decimal(value, name):
    try:
        d = Decimal(str(value))
    except Exception as exc:  # decimal.InvalidOperation and friends
        raise ValueError(f"{name}: not a number: {value!r}") from exc
    if not d.is_finite():
        raise ValueError(f"{name}: not finite")
    return d


@dataclass(frozen=True)
class Parcel:
    """Physical parcel. Weight in kg, dimensions in cm (any numeric type)."""

    weight_kg: object
    length_cm: object
    width_cm: object
    height_cm: object

    def weight(self):
        return to_decimal(self.weight_kg, "weight_kg")

    def dimensions(self):
        return (
            to_decimal(self.length_cm, "length_cm"),
            to_decimal(self.width_cm, "width_cm"),
            to_decimal(self.height_cm, "height_cm"),
        )


@dataclass(frozen=True)
class Quote:
    zone: int
    remote: bool
    billable_kg: Decimal
    transport: Decimal
    fuel: Decimal
    surcharges: Dict[str, Decimal] = field(default_factory=dict)
    total: Decimal = Decimal("0")
