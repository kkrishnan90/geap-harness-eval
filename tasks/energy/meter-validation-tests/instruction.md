# MDM-3318: Unit tests for the VEE rules before the settlement audit

**Component:** mdm-vee (`internal/vee`) · **Priority:** High · **Type:** Task (tests)

## Context

The regulator's settlement audit in March requires that every VEE
(validation, estimation, editing) rule we apply to interval meter data is
covered by automated tests. `internal/vee` implements the rules in
`docs/vee-rules.md`, but `internal/vee/vee_test.go` only checks a clean day.
Last year a refactor silently changed how short gaps were estimated and
nobody noticed for two billing cycles.

## What to do

Write **`internal/vee/rules_test.go`** (package `vee`, standard `testing`
package only) with unit tests for `Validate` and `Estimate` that pin down
**every** rule in `docs/vee-rules.md` with exact expected results, including
boundaries. The current implementation is correct: **do not modify any
non-test file** (your tests will be run against the original implementation,
and also against deliberately broken variants of it, each of which breaks
exactly one documented rule).

Things your tests must pin down (from `docs/vee-rules.md`, using
`DefaultConfig()`: 15-minute slots, `MaxWh` 25000, `FlatlineCount` 8,
`MaxInterpolate` 4):

- `MISALIGNED` readings and their exclusion from the other rules;
- `DUPLICATE`: the **first** reading for a slot is the one that is kept;
- `NEGATIVE`; `HIGH` only when strictly greater than `MaxWh`;
- `GAP` for every missing slot, including the **first and last** slot of the
  window; readings outside `[from, to)` are ignored;
- `FLATLINE` at exactly `FlatlineCount` identical non-zero consecutive
  readings (not fewer), reported once at the first slot; zero runs and runs
  interrupted by a gap are not flatlines;
- issue ordering (by `Start`, then `Code`);
- `Estimate`: linear interpolation with halves rounded **up** (e.g. between
  100 and 105 with one missing slot -> 103), only for gaps of at most
  `MaxInterpolate` slots (a 4-slot gap is filled, a 5-slot gap is not), only
  between two usable neighbours, `FlagEstimated` set.

## Acceptance criteria

- `internal/vee/rules_test.go` defines at least 8 `Test…(t *testing.T)`
  functions; all pass against the current implementation
  (`go test ./internal/vee/`).
- Breaking any single documented rule in `internal/vee` makes at least one of
  your tests fail.
- Tests are deterministic: fixed UTC timestamps, no `time.Now()`, no sleeps,
  no file system access.
- `go test ./...` stays green.

## Constraints

- Go 1.22, standard library only. Only add `internal/vee/rules_test.go`.
