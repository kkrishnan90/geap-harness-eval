"""Tariff 2026-Q3 rating rules (see docs/tariff-2026Q3.md)."""

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from .models import Parcel, Quote
from .zones import zone_for_postcode

DIM_DIVISOR = Decimal("5000")          # cm^3 per kg
WEIGHT_STEP = Decimal("0.5")           # billable weight is charged in 0.5 kg steps
MAX_BILLABLE_KG = Decimal("30")
OVERSIZE_LENGTH_CM = Decimal("120")    # longest side strictly greater -> oversize
OVERSIZE_FEE = Decimal("15.00")
REMOTE_AREA_FEE = Decimal("4.50")
FUEL_RATE = Decimal("0.12")            # on transport charge only
CENT = Decimal("0.01")

# zone -> (first 0.5 kg, each additional 0.5 kg)
ZONE_RATES = {
    1: (Decimal("4.90"), Decimal("0.60")),
    2: (Decimal("5.40"), Decimal("0.70")),
    3: (Decimal("5.90"), Decimal("0.85")),
    4: (Decimal("6.60"), Decimal("1.00")),
    5: (Decimal("7.40"), Decimal("1.20")),
}


def _check_positive(parcel: Parcel):
    w = parcel.weight()
    dims = parcel.dimensions()
    if w <= 0 or any(d <= 0 for d in dims):
        raise ValueError("weight and dimensions must be positive")
    return w, dims


def dimensional_weight(parcel: Parcel) -> Decimal:
    """Volumetric weight in kg (unrounded): L x W x H / 5000."""
    _, (l, w, h) = _check_positive(parcel)
    return l * w * h / DIM_DIVISOR


def billable_weight(parcel: Parcel) -> Decimal:
    """max(actual, dimensional), rounded UP to the next 0.5 kg step."""
    actual, _ = _check_positive(parcel)
    heavier = max(actual, dimensional_weight(parcel))
    steps = (heavier / WEIGHT_STEP).to_integral_value(rounding=ROUND_CEILING)
    billable = steps * WEIGHT_STEP
    if billable > MAX_BILLABLE_KG:
        raise ValueError(f"billable weight {billable} kg exceeds {MAX_BILLABLE_KG} kg limit")
    return billable


def quote(parcel: Parcel, dest_postcode) -> Quote:
    zone = zone_for_postcode(dest_postcode)
    billable = billable_weight(parcel)
    first, additional = ZONE_RATES[zone.number]
    extra_steps = billable / WEIGHT_STEP - 1
    transport = (first + additional * extra_steps).quantize(CENT, rounding=ROUND_HALF_UP)

    surcharges = {}
    if max(parcel.dimensions()) > OVERSIZE_LENGTH_CM:
        surcharges["oversize"] = OVERSIZE_FEE
    if zone.remote:
        surcharges["remote_area"] = REMOTE_AREA_FEE

    fuel = ((transport + sum(surcharges.values(), Decimal("0"))) * FUEL_RATE).quantize(CENT, rounding=ROUND_HALF_UP)
    total = transport + fuel + sum(surcharges.values(), Decimal("0"))
    return Quote(
        zone=zone.number,
        remote=zone.remote,
        billable_kg=billable,
        transport=transport,
        fuel=fuel,
        surcharges=surcharges,
        total=total.quantize(CENT, rounding=ROUND_HALF_UP),
    )
