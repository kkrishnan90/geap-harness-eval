"""MDMS interval export: meter_id,interval_start_utc(ISO 8601 Z),kwh"""

import csv
from datetime import datetime
from decimal import Decimal

from .intervals import Interval


def read_intervals(path, meter_id=None):
    out = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            if meter_id and row["meter_id"] != meter_id:
                continue
            start = datetime.fromisoformat(row["interval_start_utc"].replace("Z", "+00:00"))
            out.append(Interval(start, Decimal(row["kwh"])))
    return out
