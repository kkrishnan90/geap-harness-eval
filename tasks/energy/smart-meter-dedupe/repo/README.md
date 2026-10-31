# meter-ingest

SQL pipeline that turns raw smart-meter interval reads from the head-end
systems (HES) into clean readings and daily usage for billing and network
planning. Everything runs inside SQLite with the `sqlite3` CLI.

```
raw_readings  --sql/dedupe.sql-->  readings  --sql/daily_rollup.sql-->  daily_usage
                                                     ^ meter_assignments (feeder history)
```

| File | Purpose |
| --- | --- |
| `sql/schema.sql` | Tables and indexes (drop + create) |
| `sql/dedupe.sql` | Rebuilds `readings` from `raw_readings` (one row per meter + interval) |
| `sql/daily_rollup.sql` | Rebuilds `daily_usage` (one row per meter + UTC day) |
| `reports/feeder_daily.sql` | Feeder load report used by network planning |
| `reports/meter_health.sql` | Meters with poor read rates (field ops work list) |
| `bin/ingest.sh` | `bin/ingest.sh db.sqlite raw.csv assignments.csv` |
| `tests/run_cases.sh` | Fixture-based tests (see below) |

## Data conventions

* `interval_start` and `received_at` are ISO-8601 UTC text
  (`2026-03-01T00:15:00Z`), so text order equals time order.
* Energy is integer **Wh** (`wh`). Intervals are 15 minutes, 96 per UTC day.
* `quality`: `A` = actual read, `E` = estimated by the HES.
* `meter_assignments` is the feeder history of a meter: valid from
  `valid_from` (inclusive) to `valid_to` (exclusive, `NULL` = still valid), as
  UTC dates `YYYY-MM-DD`.

## Tests

Each directory in `tests/cases/` is a fixture: `input.sql` (rows for
`raw_readings` / `meter_assignments`) and `checks/<name>.sql` queries with the
expected CSV output `checks/<name>.csv` (`sqlite3 -csv -header`). The runner
builds a fresh database, runs schema, input, dedupe and rollup, then compares
every check:

```
bash tests/run_cases.sh tests/cases
```
