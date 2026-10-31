# SEC-0912: SQL injection in transaction search (pen-test finding PT-26-031, CVSS 8.6)

**Component:** statement-service (`stmtsvc/search.py`, `stmtsvc/api.py`) · **Priority:** Critical · **Type:** Security

## Context

The annual external penetration test found that the transaction search behind
the online-banking "Transactions" page builds its SQL by string formatting.
With a crafted search text (`x%') OR 1=1 OR ('`) the tester listed
transactions of **other customers' accounts**; through the `sort` parameter
they ran blind sub-queries against the `accounts` table. Customers also
report that searching for `O'Brien` gives an error page and that searching
for `50%` or `Fee_2026` returns unrelated transactions.

## Required changes

`search_transactions(conn, account_id, **filters)` and
`handle_search(conn, account_id, params)` must keep their signatures and
current results for normal input, and:

1. **Bind every value** (account id, text, category, amounts, dates, limit,
   offset) as an SQL parameter. No user-supplied value may be concatenated
   into SQL text.
2. **Search text is literal.** `text` is still a case-insensitive substring
   match on `description` or `counterparty`, but `%`, `_` and `\` in the
   user's text match themselves (e.g. `50%` matches only "50% off voucher").
   Quotes are ordinary characters (`O'Brien` works).
3. **Sort and direction come from an allowlist.** `sort` must be one of
   `booking_date`, `value_date`, `amount`, `counterparty` (exactly these
   keys; `amount` sorts by `amount_minor`). `direction` is `asc` or `desc`,
   case-insensitive. Anything else raises `SearchError`. Ties are still broken
   by `id` ascending.
4. **Validate the remaining inputs**, raising `SearchError` on violation:
   * `date_from` / `date_to` must be `YYYY-MM-DD` strings that are real
     calendar dates.
   * `limit` must be an `int` between 1 and 500 inclusive; `offset` an `int`
     ≥ 0 (strings are not accepted by `search_transactions`; the API layer
     converts query-string values with `int()`).
   * amounts keep the existing `to_minor` validation.
5. **The API never returns a 500 for bad input:** `handle_search` returns
   `{"status": 400, "error": ...}` for every invalid parameter, and
   `{"status": 200, ...}` with the matching (possibly empty) result otherwise.
6. No search, whatever the input, may return rows of another account or
   modify the database.

## Acceptance criteria

- The pen-test payloads above return no rows (text) or a `SearchError` /
  HTTP 400 (sort, direction, dates, limit, offset).
- `O'Brien`, `50%`, `Fee_2026` and `C:\temp` searches return exactly the
  matching transactions.
- All existing tests keep passing.

## Constraints

- Standard library only (`sqlite3`). Do not change the schema, `models.py`
  or public signatures.
- Tests: `python3 -m unittest discover -s tests -t .`
