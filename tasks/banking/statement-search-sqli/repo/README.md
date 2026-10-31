# statement-service

Back end of the "Transactions & Statements" page in online banking. It serves
transaction search, monthly statements and CSV export for retail current
accounts. Data comes from the core-banking nightly extract, loaded into SQLite
on each node (read-mostly; the loader is the only writer).

## Layout

| Module | Purpose |
| --- | --- |
| `stmtsvc/db.py` | Schema, connection factory, demo fixture loader |
| `stmtsvc/models.py` | `Transaction`, amount helpers (amounts are integer minor units) |
| `stmtsvc/search.py` | Transaction search used by the search box and filter panel |
| `stmtsvc/api.py` | Maps HTTP query parameters (all strings) to `search_transactions` |
| `stmtsvc/statements.py` | Monthly statement (opening/closing balance, totals) |
| `stmtsvc/export.py` | CSV export of search results |
| `stmtsvc/errors.py` | `SearchError` (client error, mapped to HTTP 400) |

## Conventions

* Python 3.11+, standard library only (`sqlite3`).
* Amounts are stored and computed as integer minor units; `Decimal` only at the edges.
* Every query is scoped to one `account_id`; the caller has already checked
  that the logged-in customer owns that account.
* Client mistakes raise `SearchError`; the API turns them into
  `{"status": 400, "error": ...}`. Anything else is a 500 and pages on-call.
* Tests: `python3 -m unittest discover -s tests -t .`
