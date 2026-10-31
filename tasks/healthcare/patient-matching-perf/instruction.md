# MPI-731: Nightly MPI linkage does not finish (quadratic pair comparisons)

**Component:** mpi-link (`mpi/linker.py`) · **Priority:** High · **Type:** Performance

## Context

The regional MPI now receives registrations from 14 hospitals. The nightly
batch (`link()`) and the online registration check
(`MasterPatientIndex.add()`) both score **every** pair of records: the batch
job did 1.9 billion comparisons last night and was killed at 06:00, and each
online registration compares against the whole index. Capacity planning
measures cost in pair comparisons (`PairScorer.comparisons`), not wall time.

## Analysis (from the data-quality team)

With the signed-off weights in `mpi/scoring.py`, a pair that does not share a
birth date **and** does not share a non-empty normalised phone
(`normalize.phone_key`) can score at most 3.0 + 1.5 + 1.5 + 0.5 = 6.5, which is
below `MATCH_THRESHOLD` (7.0). So for any threshold above 6.5, only pairs that
share a birth date or a non-empty normalised phone can match.

## Required change

Introduce blocking so that, for thresholds above 6.5:

- `link(records, scorer, threshold)` calls `scorer.score()` only for distinct
  record pairs that share a birth date (both present and equal) or a non-empty
  normalised phone, **each such pair at most once** (a pair sharing both keys
  is still scored once). Records without birth date and without a usable phone
  are never scored.
- `MasterPatientIndex.add(record)` scores the new record only against
  previously added records that share one of those keys with it, each at most
  once.
- For thresholds **at or below 6.5** (stewards' "possible match" report), keep
  the exhaustive comparison so results stay complete.

Results must be **identical** to the current implementation: same `Match`
objects (left < right, same scores), same sorting by `(left, right)`, for
`link()` and for the cumulative output of `add()`. `clusters()`, the CLI and
the report must keep working.

## Acceptance criteria

- For a synthetic population (`mpi.synth.generate(3000)`, ~4,600 records) the
  batch link completes with a `PairScorer(max_comparisons=N)` where N is the
  number of distinct pairs sharing a birth date or a non-empty normalised phone,
  and returns exactly the matches of the exhaustive algorithm.
- Same for an index built by adding records one by one.
- All existing tests keep passing.

## Constraints

- Do **not** modify `mpi/scoring.py` (owned by data quality) or
  `mpi/normalize.py`; every pair evaluation must go through
  `PairScorer.score()` (no inlined/cached scoring to dodge the counter).
- Keep public signatures of `link`, `clusters`, `MasterPatientIndex` and
  `Match` unchanged. New helper modules are fine.
- Standard library only. Tests: `python3 -m unittest discover -s tests -t .`
