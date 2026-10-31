from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class PatientRecord:
    record_id: str
    source: str            # registering system, e.g. "HOSP-A", "GPNET", "LAB"
    family: str
    given: str
    birth_date: Optional[date]
    sex: str = "U"         # F / M / X / U
    postcode: str = ""
    phone: str = ""
