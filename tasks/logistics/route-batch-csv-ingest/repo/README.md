# routebatch

Ingests the nightly route batch exports (CSV) produced by the dispatch
planning tool and turns them into `RouteBatch` objects for the driver app
backend and the depot loading-sequence printer.

## Layout

```
src/routebatch/
  models.py     Stop / RouteBatch value objects
  dialect.py    CSV dialect helpers (delimiter sniffing, header normalisation)
  ingest.py     load_batch() / parse_batch(): CSV -> RouteBatch, with line-numbered errors
  timewin.py    delivery time window parsing ("08:00-12:00")
  planner.py    per-route grouping, sequencing checks, loading order
  geo.py        haversine distance helpers
tools/lint.py   stdlib-only lint run in CI
scripts/ci.sh   the CI entrypoint (lint + full unit test suite)
tests/          unittest suites, fixtures in tests/fixtures/
```

## Conventions

* Python 3.11+, standard library only (the backend image has no pip access).
* Test modules are `tests/test_*.py`; every test module must run in CI.
* Tests must pass from any working directory and with any `PYTHONHASHSEED`.
* `scripts/ci.sh` is exactly what the pipeline runs. Run it locally before
  pushing:

```
bash scripts/ci.sh
```
