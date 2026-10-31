"""Rate tables, transcribed from the RATETAB working-storage table in legacy/PRMRATE.cbl."""

from decimal import Decimal

# Premium rate per mille of sum insured, by product and risk class.
RATE_PER_MILLE = {
    "MTR": {"A": Decimal("18.50"), "B": Decimal("22.75"), "C": Decimal("27.40"),
            "D": Decimal("34.10"), "E": Decimal("45.00")},
    "HOM": {"A": Decimal("1.25"), "B": Decimal("1.60"), "C": Decimal("2.10"),
            "D": Decimal("2.85"), "E": Decimal("3.90")},
    # TODO(port): TRV (travel) table still to be transcribed from RATETAB
}

MINIMUM_PREMIUM = {"MTR": Decimal("150.00"), "HOM": Decimal("90.00")}

YOUNG_DRIVER_AGE = 25        # MTR only: age < 25
YOUNG_DRIVER_LOADING = 35    # percent
SENIOR_DRIVER_AGE = 70       # MTR only: age over 70
SENIOR_DRIVER_LOADING = 20   # percent
CLAIM_LOADING = 10           # percent per prior claim, all products
MAX_CLAIMS_LOADED = 5


def products():
    return sorted(RATE_PER_MILLE)
