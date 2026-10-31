# parcelrate

Domestic parcel rating library used by the shipping desk (`ship-desk`) and the
nightly invoice reconciliation job. It turns a parcel (weight + dimensions) and
a destination postcode into a price quote.

| Module | Purpose |
| --- | --- |
| `parcelrate/models.py` | `Parcel` and `Quote` value objects |
| `parcelrate/zones.py` | Postcode -> rating zone (1..5) and remote-area flag |
| `parcelrate/rates.py` | Billable weight and quote calculation (tariff 2026-Q3) |
| `parcelrate/labels.py` | Label text formatting (unrelated to pricing) |
| `parcelrate/tracking.py` | Tracking number check digit (mod-11) |
| `docs/tariff-2026Q3.md` | The tariff sheet as published to customers |

## Conventions

* Python 3.11+, standard library only.
* Money and weights are `decimal.Decimal`. Never use floats for money.
* Errors on invalid input are `ValueError`.
* Tests use `unittest` and live in `tests/test_<module>.py`:

```
python3 -m unittest discover -s tests -t .
```
