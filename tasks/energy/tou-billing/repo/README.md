# meterbill

Billing engine for residential **time-of-use (TOU)** tariffs. Interval data
(15-minute kWh reads) arrives from the meter data management system (MDMS) in
UTC; tariffs are defined in the utility's local time.

| Module | Purpose |
| --- | --- |
| `meterbill/intervals.py` | `Interval` (UTC start, kWh) and helpers |
| `meterbill/tariff.py` | `TouTariff`, `Band`, the published residential tariffs |
| `meterbill/billing.py` | `compute_bill()` - band assignment, bill lines, daily charge |
| `meterbill/holidays.py` | Utility holiday calendar (off-peak all day) |
| `meterbill/validation.py` | Interval data quality checks (gaps, negatives, duplicates) |
| `meterbill/tax.py` | Sales tax on a bill total |
| `meterbill/csvio.py` | MDMS CSV import |

## Conventions

* Python 3.11+, standard library only (`zoneinfo` for time zones).
* Money and energy are `decimal.Decimal`, never float.
* All datetimes are timezone-aware; interval starts are UTC.
* Tests: `python3 -m unittest discover -s tests -t .`
