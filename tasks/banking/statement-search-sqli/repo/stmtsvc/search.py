"""Transaction search (search box + filter panel)."""

from .errors import SearchError
from .models import COLUMNS, row_to_transaction, to_minor

DEFAULT_LIMIT = 50
MAX_LIMIT = 500


def search_transactions(conn, account_id, *, text=None, category=None, min_amount=None,
                        max_amount=None, date_from=None, date_to=None,
                        sort="booking_date", direction="desc", limit=DEFAULT_LIMIT, offset=0):
    """Return the account's transactions matching all given filters.

    text       case-insensitive substring of description or counterparty
    category   exact category
    min/max    amount bounds in major units (inclusive, signed)
    date_*     inclusive ISO booking-date bounds (YYYY-MM-DD)
    sort       booking_date | value_date | amount | counterparty
    direction  asc | desc; ties are broken by id ascending
    """
    where = [f"account_id = '{account_id}'"]
    if text:
        where.append(f"(description LIKE '%{text}%' OR counterparty LIKE '%{text}%')")
    if category:
        where.append(f"category = '{category}'")
    if min_amount is not None:
        where.append(f"amount_minor >= {to_minor(min_amount)}")
    if max_amount is not None:
        where.append(f"amount_minor <= {to_minor(max_amount)}")
    if date_from:
        where.append(f"booking_date >= '{date_from}'")
    if date_to:
        where.append(f"booking_date <= '{date_to}'")

    sort_column = "amount_minor" if sort == "amount" else sort
    if int(limit) > MAX_LIMIT:
        raise SearchError(f"limit must be at most {MAX_LIMIT}")

    sql = (
        f"SELECT {', '.join(COLUMNS)} FROM transactions WHERE {' AND '.join(where)} "
        f"ORDER BY {sort_column} {direction}, id ASC LIMIT {limit} OFFSET {offset}"
    )
    return [row_to_transaction(r) for r in conn.execute(sql).fetchall()]


def count_transactions(conn, account_id, **filters):
    filters.pop("limit", None)
    filters.pop("offset", None)
    return len(search_transactions(conn, account_id, limit=MAX_LIMIT, **filters))
