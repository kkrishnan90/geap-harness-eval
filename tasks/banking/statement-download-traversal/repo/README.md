# estatements

Serves archived PDF account statements to the online-banking front end.
The statement renderer writes one PDF per account and month into the archive
volume; this service only reads from it.

## Layout

| Package | Purpose |
| --- | --- |
| `internal/archive` | Read-only access to the statement archive volume |
| `internal/httpapi` | HTTP handlers (`GET /statements/download?file=...`) |
| `internal/naming` | Archive naming convention: `<customer>/<yyyy>/<yyyy-mm>_<account>.pdf` |
| `internal/audit` | Download audit trail (who downloaded what, when) |
| `cmd/estatements` | Server binary |

## Conventions

* Go 1.22, standard library only.
* The gateway authenticates the customer and passes the id in the
  `X-Customer-ID` header; handlers must only serve files under that
  customer's directory.
* `archive` errors are sentinel values (`ErrNotFound`, `ErrInvalidName`);
  handlers map them to 404 / 400. Never leak filesystem paths in responses.
* Tests: `go test ./...`
