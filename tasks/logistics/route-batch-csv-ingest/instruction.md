# DISP-977: routebatch CI is red, and it has been lying to us for weeks

**Component:** routebatch (`scripts/ci.sh`, `tests/`, `src/routebatch/`) · **Priority:** High · **Type:** Bug / CI

## Context

The `routebatch` pipeline step (`bash scripts/ci.sh`) has been red since the
repo was moved to the `src/` layout. Before that it was green, but it turns out
it was only ever running a fraction of the test suite: whole test modules were
never collected. Meanwhile the Munich and Berlin depots report that their
nightly exports fail to import:

* Munich exports are UTF-8 **with a BOM** (Excel "CSV UTF-8").
* Berlin exports are **semicolon**-separated (German Excel locale).
* Driver notes may contain **line breaks inside quoted fields**.

The tests describing exactly these cases already exist in `tests/` but have
never run in CI.

## What to do

1. Make `bash scripts/ci.sh` pass again, running the lint step **and every
   test module in `tests/`** (`tests_models.py`, `test_ingest.py`,
   `test_planner.py`). The tests must pass:
   * when `scripts/ci.sh` is invoked from **any working directory**, and
   * for **any** `PYTHONHASHSEED` value.
2. Fix the ingest code so that the existing tests pass, i.e. implement:
   * **BOM:** `load_batch(path)` and `parse_batch(text)` accept input starting
     with a UTF-8 BOM (the BOM is not part of the first column name).
   * **Delimiter detection** from the header line: the delimiter is the most
     frequent of `,`, `;` and TAB in the header line; on a tie, prefer `,`
     then `;` then TAB. `RouteBatch.delimiter` reports the detected one.
   * **Quoted fields** may contain the delimiter and line breaks (`\n` or
     `\r\n`); such a record is one stop.
   * **Line numbers:** `IngestError.line` (and the `"line <n>: "` message
     prefix) is the 1-based **physical** line number where the offending record
     *starts* (header is line 1; a record spanning lines 2-4 is line 2; the next
     record is line 5). Missing-column errors stay on line 1.

## Acceptance criteria

- `bash scripts/ci.sh` exits 0 from any cwd and with any hash seed; its
  output shows the lint (`lint: 0 finding(s)`) and the unittest run in
  verbose mode (`-v`, one `... ok` line per test).
- No existing test is deleted, renamed, skipped or weakened (fixing *how* a
  test locates its fixtures or compares unordered results is fine).
- Comma and TAB exports keep working exactly as before.

## Constraints

- Standard library only. Keep the public API (`load_batch`, `parse_batch`,
  `IngestError`, `RouteBatch`, `Stop`) unchanged.
- Keep `tools/lint.py` and its rules as they are; fix the code instead.
