# mediation – CDR rating

Rating stage of the Telcoridge mediation pipeline. Collected and correlated
CDRs (call detail records) from the MSC/IMS come in as CSV; this module prices
each call against the subscriber's tariff plan and hands rated records to
billing.

## Packages

| Package | Purpose |
| --- | --- |
| `internal/money` | Fixed-point money (`Money`, 1/10000 of the currency unit) |
| `internal/cdr` | CDR record type and CSV decoder (`ParseCSV`) |
| `internal/rating` | Tariff plans and rating engines (`FlatPlan`, zone lookup) |
| `cmd/rater` | Batch CLI: `go run ./cmd/rater -plan testdata/flat.json < calls.csv` |

## Conventions

* Go 1.22+, standard library only (the rating nodes are air-gapped).
* Money is always `money.Money` (int64, 4 decimals). Never use floats for
  amounts. Rounding is **half-up, once per rated call** unless a plan says otherwise.
* Durations in CDRs are whole seconds. Times are instants (`time.Time`);
  tariff rules that depend on wall-clock time use the plan's own time zone.
* Tariff files are JSON (`encoding/json`), money values are decimal strings
  (`"0.0900"`) to avoid float parsing.
* Exported API of `internal/rating` is used by the billing adapter; extend it,
  do not break it.
* Tests: `go test ./...`
