# RET-2291: Promotions end an hour early/late after DST changes; shelf labels show wrong "days left"

**Component:** promo-engine (`promo_engine/validity.py`) · **Priority:** High · **Type:** Bug

## Context

Store-operations raised several incidents after the last clock change:

* Berlin (`DE-BER-001`): the "AUTUMN20" coupon valid until **31 October**
  stopped working at 23:00 local time on 31 October; customers at the late
  checkout were refused the discount.
* New York (`US-NYC-014`): a promotion valid until **15 March** was still
  being applied at 00:30 on 16 March.
* Sydney: same symptom as Berlin after the April change.
* Several stores report coupons failing in the very last second of the expiry
  day.
* Shelf labels in the US show one day less "days left" in the evening, because
  the count rolls over at UTC midnight instead of the store's midnight.

Checkout servers run in UTC; the store's zone is passed to the validity
functions as a `zoneinfo.ZoneInfo`.

## Expected behaviour

For a promotion with `starts_on = S` and `expires_on = E` (calendar dates,
both inclusive) and a store in zone `tz`:

* `promo_window(promo, tz)` returns `(start, end)` as **timezone-aware UTC**
  datetimes where `start` is local midnight at the beginning of `S` and `end`
  is local midnight at the beginning of the day after `E` (exclusive). Each
  boundary must use the UTC offset actually in force in `tz` on that date
  (DST transitions inside the window must not shift the end).
* `is_active(promo, at, tz)` is `start <= at < end`, so it is active during the
  whole of the last local day, including its final second (sub-second
  precision included) and inactive from local midnight after `E`.
* `days_remaining(promo, at, tz)` is `(E - local_date).days` floored at 0,
  where `local_date` is the calendar date of `at` **in the store's zone**.
* `is_active` and `days_remaining` raise `ValueError` when `at` is a naive
  datetime (no tzinfo) instead of silently assuming the server's zone.

## Acceptance criteria

* Berlin, valid 20-31 Oct 2026: active at 23:30 local on 31 Oct, inactive at
  00:00 local on 1 Nov.
* New York, valid 1-15 Mar 2026: window end is `2026-03-16 04:00 UTC`.
* Pricing (`price_cart`) applies promotions according to the corrected rules.
* All existing tests keep passing.

## Constraints

* Do not change public signatures in `promo_engine` (POS clients import them).
* Standard library only; do not hard-code UTC offsets or DST dates.
* Tests: `python3 -m unittest discover -s tests -t .`
