"""Monthly statements."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class MonthlyStatement:
    account_id: str
    month: str               # YYYY-MM
    opening_minor: int
    credits_minor: int
    debits_minor: int
    closing_minor: int
    transaction_count: int


def _month_bounds(month):
    year, mon = (int(x) for x in month.split("-"))
    start = date(year, mon, 1)
    end = date(year + (mon == 12), mon % 12 + 1, 1)
    return start.isoformat(), end.isoformat()


def monthly_statement(conn, account_id, month, opening_balance_minor=0):
    start, end = _month_bounds(month)
    prior = conn.execute(
        "SELECT COALESCE(SUM(amount_minor), 0) FROM transactions WHERE account_id = ? AND booking_date < ?",
        (account_id, start),
    ).fetchone()[0]
    credits, debits, n = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN amount_minor > 0 THEN amount_minor END), 0),"
        "       COALESCE(SUM(CASE WHEN amount_minor < 0 THEN amount_minor END), 0), COUNT(*)"
        " FROM transactions WHERE account_id = ? AND booking_date >= ? AND booking_date < ?",
        (account_id, start, end),
    ).fetchone()
    opening = opening_balance_minor + prior
    return MonthlyStatement(account_id, month, opening, credits, debits, opening + credits + debits, n)
