# ING-412: Daily usage wrong after HES resends; meters double counted after feeder moves

**Component:** meter-ingest (`sql/dedupe.sql`, `sql/daily_rollup.sql`) · **Priority:** High · **Type:** Bug

## Context

Billing and network planning both consume `daily_usage`. Three issues were
reported after the head-end system (HES) upgrade, which resends intervals much
more often:

1. **Wrong reading kept on resends.** When the HES resends an interval (retry,
   corrected actual, re-estimation), `readings` keeps the *first* delivery. A
   late actual read never replaces an earlier estimate, and "no data" rows
   (`wh` NULL) can end up in the selection.
2. **Double counting.** Meters that moved to another feeder have every day
   counted once per feeder they were ever assigned to, which inflates the
   feeder load report.
3. **NULL counters.** Days with no estimated (or no actual) intervals get
   `NULL` instead of `0` in `estimated_intervals` / `actual_intervals`,
   breaking the billing extract.

## Expected behaviour

`sql/dedupe.sql` rebuilds `readings` from `raw_readings` with exactly one row
per `(meter_id, interval_start)`, chosen as follows:

1. Rows with `wh IS NULL` are ignored completely (an interval that only has
   NULL rows has no reading).
2. An actual read (`quality = 'A'`) always wins over an estimate (`'E'`),
   whatever the delivery order.
3. Among rows of the same quality, the latest `received_at` wins.
4. If still tied, the row inserted into `raw_readings` last wins.

The kept row's `wh`, `quality` and `received_at` are copied unchanged.

`sql/daily_rollup.sql` rebuilds `daily_usage` with one row per meter and UTC
day (`substr(interval_start, 1, 10)`) that has at least one reading:

- `feeder_id` is the `meter_assignments` row valid **on that day**
  (`valid_from <= day`, and `valid_to IS NULL OR day < valid_to`); `NULL` if
  the meter has no assignment valid that day. Each meter-day is counted once.
- `wh_total` = sum of `wh`; `actual_intervals` / `estimated_intervals` = number
  of readings with that quality (integers, `0` when none, never `NULL`);
  `missing_intervals` = 96 − number of readings.

Both scripts must be re-runnable: running them again on the same data gives
the same result.

## Acceptance criteria

- The fixtures in `tests/cases` keep passing (`bash tests/run_cases.sh tests/cases`).
- `reports/feeder_daily.sql` shows each meter-day under exactly one feeder.

## Constraints

- Do not change `sql/schema.sql`, the reports, or table/column names
  (downstream extracts read them).
- Plain SQLite SQL, run with the `sqlite3` CLI (window functions are available).
