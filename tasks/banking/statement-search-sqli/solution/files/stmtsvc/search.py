"""Transaction search (search box + filter panel).

All user-supplied values are bound as SQL parameters. Identifiers that cannot be
bound (sort column, direction) come from fixed allowlists.
"""

import re
from datetime import date

from .errors import SearchError
from .models import COLUMNS, row_to_transaction, to_minor

DEFAULT_LIMIT = 50
MAX_LIMIT = 500

SORT_COLUMNS = {
    "booking_date": "booking_date",
    "value_date": "value_date",
    "amount": "amount_minor",
    "counterparty": "counterparty",
}
DIRECTIONS = {"asc": "ASC", "desc": "DESC"}

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _like_pattern(text):
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _iso_date(name, value):
    if not isinstance(value, str) or not _ISO_DATE.match(value):
        raise SearchError(f"{name} must be YYYY-MM-DD")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise SearchError(f"{name} is not a valid date") from None
    return value


def _int_param(name, value, minimum, maximum=None):
    if isinstance(value, bool) or not isinstance(value, int):
        raise SearchError(f"{name} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        raise SearchError(f"{name} out of range")
    return value


def search_transactions(conn, account_id, *, text=None, category=None, min_amount=None,
                        max_amount=None, date_from=None, date_to=None,
                        sort="booking_date", direction="desc", limit=DEFAULT_LIMIT, offset=0):
    """Return the account's transactions matching all given filters.

    text       case-insensitive substring of description or counterparty (literal, no wildcards)
    category   exact category
    min/max    amount bounds in major units (inclusive, signed)
    date_*     inclusive ISO booking-date bounds (YYYY-MM-DD)
    sort       booking_date | value_date | amount | counterparty
    direction  asc | desc (case-insensitive); ties are broken by id ascending
    """
    where = ["account_id = ?"]
    params = [account_id]
    if text:
        where.append("(description LIKE ? ESCAPE '\\' OR counterparty LIKE ? ESCAPE '\\')")
        pattern = _like_pattern(text)
        params += [pattern, pattern]
    if category:
        where.append("category = ?")
        params.append(category)
    if min_amount is not None:
        where.append("amount_minor >= ?")
        params.append(to_minor(min_amount))
    if max_amount is not None:
        where.append("amount_minor <= ?")
        params.append(to_minor(max_amount))
    if date_from:
        where.append("booking_date >= ?")
        params.append(_iso_date("date_from", date_from))
    if date_to:
        where.append("booking_date <= ?")
        params.append(_iso_date("date_to", date_to))

    if sort not in SORT_COLUMNS:
        raise SearchError(f"unsupported sort key: {sort!r}")
    if not isinstance(direction, str) or direction.lower() not in DIRECTIONS:
        raise SearchError(f"unsupported direction: {direction!r}")
    limit = _int_param("limit", limit, 1, MAX_LIMIT)
    offset = _int_param("offset", offset, 0)

    sql = (
        f"SELECT {', '.join(COLUMNS)} FROM transactions WHERE {' AND '.join(where)} "
        f"ORDER BY {SORT_COLUMNS[sort]} {DIRECTIONS[direction.lower()]}, id ASC LIMIT ? OFFSET ?"
    )
    params += [limit, offset]
    return [row_to_transaction(r) for r in conn.execute(sql, params).fetchall()]


def count_transactions(conn, account_id, **filters):
    filters.pop("limit", None)
    filters.pop("offset", None)
    return len(search_transactions(conn, account_id, limit=MAX_LIMIT, **filters))
