"""Daily redemption summaries for the merchandising team."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, Iterable, Tuple


@dataclass(frozen=True)
class Redemption:
    store_id: str
    code: str
    business_date: date
    discount: Decimal


def summarize(redemptions: Iterable[Redemption]) -> Dict[Tuple[date, str], dict]:
    """Group by (business_date, code): count and total discount."""
    out: Dict[Tuple[date, str], dict] = defaultdict(lambda: {"count": 0, "discount": Decimal("0"), "stores": set()})
    for r in redemptions:
        row = out[(r.business_date, r.code)]
        row["count"] += 1
        row["discount"] += r.discount
        row["stores"].add(r.store_id)
    return dict(out)


def to_csv_rows(summary) -> list:
    rows = [("business_date", "code", "count", "discount", "stores")]
    for (day, code), row in sorted(summary.items()):
        rows.append((day.isoformat(), code, str(row["count"]), f"{row['discount']:.2f}", str(len(row["stores"]))))
    return rows
