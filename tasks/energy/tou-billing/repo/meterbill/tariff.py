"""Tariff definitions. Band times are local wall-clock times of the tariff zone."""

from dataclasses import dataclass, field
from datetime import time
from decimal import Decimal
from typing import Tuple


@dataclass(frozen=True)
class Band:
    code: str                      # bill line code, e.g. "PEAK"
    description: str
    rate: Decimal                  # per kWh
    windows: Tuple[Tuple[time, time], ...] = ()   # [start, end) local; end time(0) = midnight
    weekdays_only: bool = True


@dataclass(frozen=True)
class TouTariff:
    code: str
    zone: str                      # IANA zone, e.g. "America/Chicago"
    bands: Tuple[Band, ...]        # checked in order; first matching window wins
    default_band: Band             # everything not covered (and weekends/holidays)
    daily_charge: Decimal
    holidays: frozenset = field(default_factory=frozenset)

    @property
    def all_bands(self):
        return self.bands + (self.default_band,)


RESIDENTIAL_TOU_2026 = TouTariff(
    code="RES-TOU-2026",
    zone="America/Chicago",
    bands=(
        Band("PEAK", "On-peak energy", Decimal("0.28417"), ((time(16), time(20)),)),
        Band("SHOULDER", "Mid-peak energy", Decimal("0.14905"),
             ((time(7), time(16)), (time(20), time(22)))),
    ),
    default_band=Band("OFFPEAK", "Off-peak energy", Decimal("0.07215"), weekdays_only=False),
    daily_charge=Decimal("0.4931"),
)


# EV owners: super off-peak overnight window, every day of the week.
RESIDENTIAL_EV_2026 = TouTariff(
    code="RES-EV-2026",
    zone="America/Chicago",
    bands=(
        Band("EVNIGHT", "Super off-peak (EV) energy", Decimal("0.04110"),
             ((time(23), time(5)),), weekdays_only=False),
        Band("PEAK", "On-peak energy", Decimal("0.31250"), ((time(16), time(20)),)),
    ),
    default_band=Band("OFFPEAK", "Off-peak energy", Decimal("0.08875"), weekdays_only=False),
    daily_charge=Decimal("0.6575"),
)
