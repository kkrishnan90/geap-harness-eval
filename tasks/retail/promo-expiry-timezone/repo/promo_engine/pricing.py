"""Applies active promotions to a cart."""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, List

from .models import Cart, Promotion
from .stores import get_store
from .validity import is_active

CENT = Decimal("0.01")


@dataclass(frozen=True)
class AppliedDiscount:
    code: str
    amount: Decimal


@dataclass(frozen=True)
class PricedCart:
    subtotal: Decimal
    discounts: List[AppliedDiscount]

    @property
    def total(self) -> Decimal:
        return self.subtotal - sum((d.amount for d in self.discounts), Decimal("0"))


def _eligible_amount(cart: Cart, promo: Promotion) -> Decimal:
    if promo.sku_prefix is None:
        return cart.subtotal
    return sum((l.total for l in cart.lines if l.sku.startswith(promo.sku_prefix)), Decimal("0"))


def price_cart(cart: Cart, promotions: Iterable[Promotion], at: datetime) -> PricedCart:
    """Apply every active promotion (non-stacking per code) in code order."""
    store = get_store(cart.store_id)
    discounts = []
    remaining = cart.subtotal
    seen = set()
    for promo in sorted(promotions, key=lambda p: p.code):
        if promo.code in seen or not is_active(promo, at, store.tz):
            continue
        seen.add(promo.code)
        if cart.subtotal < promo.min_basket:
            continue
        base = _eligible_amount(cart, promo)
        amount = (base * promo.percent_off / 100 + promo.amount_off).quantize(CENT, ROUND_HALF_UP)
        amount = min(amount, base, remaining)
        if amount > 0:
            discounts.append(AppliedDiscount(promo.code, amount))
            remaining -= amount
    return PricedCart(cart.subtotal.quantize(CENT, ROUND_HALF_UP), discounts)
