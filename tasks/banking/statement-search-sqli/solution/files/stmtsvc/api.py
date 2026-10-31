"""HTTP adapter: query-string parameters (strings) -> search_transactions."""

from .errors import SearchError
from .search import DEFAULT_LIMIT, search_transactions

_FILTERS = ("text", "category", "min_amount", "max_amount", "date_from", "date_to", "sort", "direction")


def handle_search(conn, account_id, params):
    """Return a JSON-serialisable response dict.

    200: {"status": 200, "items": [...], "count": n}
    400: {"status": 400, "error": "<message>"}
    """
    kwargs = {k: params[k] for k in _FILTERS if params.get(k) not in (None, "")}
    try:
        kwargs["limit"] = int(params.get("limit", DEFAULT_LIMIT))
        kwargs["offset"] = int(params.get("offset", 0))
    except (TypeError, ValueError):
        return {"status": 400, "error": "limit/offset must be integers"}
    try:
        items = search_transactions(conn, account_id, **kwargs)
    except SearchError as e:
        return {"status": 400, "error": str(e)}
    return {"status": 200, "items": [t.as_dict() for t in items], "count": len(items)}
