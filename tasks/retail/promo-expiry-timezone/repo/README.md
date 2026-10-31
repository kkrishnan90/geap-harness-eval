# promo-engine

Promotion evaluation used by the POS fleet and the web checkout of the store
network. Every store evaluates promotions on its own wall clock: a coupon
"valid until 15 March" is valid until midnight at the end of 15 March *in the
store's time zone*, wherever the request is processed.

## Layout

| Module | Purpose |
| --- | --- |
| `promo_engine/models.py` | `Promotion`, `CartLine`, `Cart` value objects |
| `promo_engine/stores.py` | Store directory (store id -> IANA time zone, currency) |
| `promo_engine/validity.py` | Promotion validity windows (`promo_window`, `is_active`, `days_remaining`) |
| `promo_engine/pricing.py` | Applies active promotions to a cart |
| `promo_engine/coupons.py` | Coupon code format and check character |
| `promo_engine/reporting.py` | Daily redemption summaries for merchandising |

## Conventions

* Python 3.11+, standard library only (`zoneinfo` for time zones).
* All instants crossing module boundaries are **timezone-aware** `datetime`s.
  Promotion start/expiry are calendar `date`s interpreted in the store's zone.
* Never call `datetime.now()` inside library code; callers pass `at=`.
* Money is `decimal.Decimal`, rounded half-up to cents.
* Tests: `python3 -m unittest discover -s tests -t .`
