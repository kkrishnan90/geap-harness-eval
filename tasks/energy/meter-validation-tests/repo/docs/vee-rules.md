# VEE rules (MDM release 2026.2)

Applies to 15-minute interval energy readings (Wh) inside a validation
window `[from, to)`. See `internal/vee` for the implementation.

## Validation (`Validate`)

| Code | Rule |
| --- | --- |
| `MISALIGNED` | `Start` is not a multiple of `Config.Interval` since the Unix epoch (UTC). The reading is ignored by all other rules. |
| `DUPLICATE` | A second (or later) reading with the same `Start` as an earlier one, in input order. Only the first is kept; later ones are ignored by other rules. |
| `NEGATIVE` | `Wh < 0`. |
| `HIGH` | `Wh > Config.MaxWh` (strictly greater; equal is fine). |
| `GAP` | An interval slot in `[from, to)` without a reading. One issue per missing slot, including at the start and the end of the window. |
| `FLATLINE` | `Config.FlatlineCount` or more readings in **consecutive** slots (no gap between them) with the **same non-zero** value. Reported once, at the first slot of the run. Zero readings never form a flatline (no consumption at night is normal). |

Readings outside `[from, to)` are ignored. Issues are returned sorted by
`Start`, then by `Code` (string order).

## Estimation (`Estimate`)

For every maximal run of `k` consecutive missing slots inside `[from, to)`:

* only if `k <= Config.MaxInterpolate` **and** there is an accepted reading in
  the slot immediately before and immediately after the run, both with
  `0 <= Wh <= MaxWh`;
* the i-th missing slot (1-based) gets
  `prev + (next - prev) * i / (k + 1)`, rounded to the nearest Wh, halves
  rounded up;
* estimated readings carry `FlagEstimated`.

Runs at the window edges, longer runs, or runs next to an invalid reading are
left as gaps. `Estimate` returns only the new readings, sorted by `Start`.
