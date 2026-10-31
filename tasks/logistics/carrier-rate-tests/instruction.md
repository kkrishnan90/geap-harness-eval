# SHIP-1840: Add unit tests for parcel rating before the Q4 tariff change

**Component:** parcelrate (`parcelrate/rates.py`) · **Priority:** Medium · **Type:** Task (tests)

## Context

`parcelrate/rates.py` prices every parcel the shipping desk sends, but it has
no tests at all. Last quarter two invoice disputes came from regressions in
this module that nobody noticed for weeks. Before finance hands us the Q4
tariff, we want a test suite that pins down the **current** 2026-Q3 rules, so
any regression in them fails CI.

## What to do

Create **`tests/test_rates.py`** (unittest, standard library only) with tests
for `dimensional_weight`, `billable_weight` and `quote`. The current
implementation is correct; **do not change anything under `parcelrate/`**
(your tests will be run against the original implementation, and also
against deliberately broken variants of it).

The rules your tests must pin down (all of these are current behaviour):

1. **Dimensional weight** = length x width x height (cm) / **5000**, in kg,
   unrounded.
2. **Billable weight** = the larger of actual and dimensional weight,
   rounded **up** to the next 0.5 kg step (1.1 kg -> 1.5 kg, 1.6 kg -> 2.0 kg;
   an exact step such as 2.5 kg stays 2.5 kg). The minimum is therefore 0.5 kg.
3. Billable weight above **30 kg** raises `ValueError`; exactly 30 kg is
   allowed. The limit applies to the *billable* weight, so a light but bulky
   parcel can exceed it. Non-positive weight or dimensions raise `ValueError`.
4. **Transport charge** = zone price for the first 0.5 kg + the zone's price for
   each additional 0.5 kg (table in `rates.py` / `docs/tariff-2026Q3.md`).
5. **Fuel surcharge** = 12 % of the transport charge **only** (not of other
   surcharges), rounded half-up to the cent.
6. **Oversize** surcharge EUR 15.00 when the longest side is **strictly
   greater** than 120 cm (exactly 120 cm is not oversize). Key `"oversize"` in
   `Quote.surcharges`.
7. **Remote area** surcharge EUR 4.50 for postcodes in
   `zones.REMOTE_POSTCODES` (key `"remote_area"`).
8. `Quote.total` = transport + fuel + all surcharges.

Worked example: a 1.1 kg parcel of 10x10x10 cm to `44135` (zone 1) is billed
at 1.5 kg; transport 6.10, fuel 0.73, no surcharges, total 6.83.

## Acceptance criteria

- `tests/test_rates.py` contains at least 8 test methods and all of them pass
  against the current implementation.
- The suite fails if any single one of the rules above is broken in
  `rates.py` (assert exact `Decimal` values, including boundary cases).
- Existing tests keep passing:
  `python3 -m unittest discover -s tests -t .`

## Constraints

- No changes to `parcelrate/`; standard library only; tests must be
  deterministic and must not depend on file system state or the clock.
