# BILL-1184: TOU bills wrong after daylight-saving changes; EV night band never applied

**Component:** meterbill (`meterbill/billing.py`) · **Priority:** High · **Type:** Bug

## Context

Customer care escalated a batch of March and November residential TOU bills.
Findings so far:

- From the second Sunday of March, usage at 16:00-17:00 local time is billed
  as mid-peak instead of on-peak (and similar one-hour shifts at every band
  edge) until the end of the billing month. November has the mirror problem.
- Bills containing the 23-hour spring day are short one daily supply charge;
  25-hour days lose usage.
- Customers on the new EV tariff (`RESIDENTIAL_EV_2026`, super off-peak
  23:00-05:00) get no `EVNIGHT` usage at all.
- Several bill lines are a cent off compared with the regulator's reference
  calculator, and kWh quantities on bills are rounded.

## Expected behaviour of `compute_bill(tariff, intervals, first_day, last_day)`

1. Each interval is assigned using the **local wall-clock time of its own
   start** in `tariff.zone` (IANA zone; the UTC offset changes during the
   period). An interval belongs to the bill if the **local date** of its start
   is within `first_day..last_day` (inclusive); others are ignored.
2. Band windows are half-open `[start, end)` local times. `end == time(0)`
   means midnight. A window with `end < start` wraps past midnight
   (`23:00-05:00` covers 23:00-23:59 and 00:00-04:59). Bands are checked in
   tariff order and the first match wins; weekday-only bands do not apply on
   Saturdays, Sundays or `tariff.holidays`; everything else is the default band.
3. Bill lines, in order: one energy line per band of `tariff.all_bands`
   (`bands` then `default_band`, also when its quantity is 0), then `DAILY`.
4. Energy line `quantity` is the **exact** `Decimal` sum of the interval kWh
   (no rounding); `amount = quantity × rate` rounded to cents with
   `ROUND_HALF_UP`.
5. `DAILY` quantity is the number of local calendar days in the period
   (`last_day - first_day + 1`, regardless of 23/25-hour days); amount =
   days × `daily_charge`, rounded to cents `ROUND_HALF_UP`.
6. No floating point anywhere in the calculation.

## Acceptance criteria

- March 2026 and November 2026 bills (America/Chicago) bill every interval in
  the right band and the right number of days.
- `RESIDENTIAL_EV_2026` bills 6 kWh of `EVNIGHT` for a flat 0.25 kWh/interval day.
- A line whose exact amount is 2.675 is billed 2.68.
- Existing tests keep passing; `Bill`, `BillLine`, `compute_bill` and
  `band_for` keep their signatures.

## Constraints

- Standard library only (`zoneinfo`, `decimal`). Do not change the tariff definitions.
- Tests: `python3 -m unittest discover -s tests -t .`
