# RAT-1543: Tiered business tariff (peak/off-peak, volume tiers, billing increments)

**Component:** mediation – `internal/rating` · **Priority:** High · **Type:** Story

## Context

Product is launching the *Business Tier 2026* voice plans. Unlike the legacy
`FlatPlan` (per-second, per-zone), these plans price every call by **time band**
(peak / off-peak), by **monthly usage tier** (minutes get cheaper after the
first N minutes in the month) and with **billing increments** such as 30/6.
Billing needs the rating engine for this before the tariff go-live. Destination
zones are not used by these plans (all destinations rate the same).

## Scope

Add the following to package `internal/rating` (keep everything that exists
working unchanged; you may add files and helpers freely):

### Billing increments

```go
type Increment struct { Initial, Subsequent int64 } // seconds
func ParseIncrement(s string) (Increment, error)      // "initial/subsequent", e.g. "30/6"
func (inc Increment) Billable(durationSec int64) int64
```

* `ParseIncrement`: exactly two positive integers separated by `/`; anything
  else is an error.
* `Billable`: `0` for a duration `<= 0`; `Initial` when the duration is at most
  `Initial`; otherwise `Initial` plus the remainder rounded **up** to a multiple
  of `Subsequent` (30/6: 31 s → 36 s; 60/60: 61 s → 120 s).

### Plan

```go
const BandPeak = "peak"; const BandOffPeak = "offpeak"

type Tier struct {
    UpToSeconds int64       // cumulative billable seconds in the cycle up to which this tier applies; 0 = unlimited (last tier)
    Peak        money.Money // per-minute rate
    OffPeak     money.Money // per-minute rate
}

type TieredPlan struct {
    Code          string
    Location      *time.Location
    PeakStartHour int              // inclusive, local hour
    PeakEndHour   int              // exclusive, local hour
    Holidays      map[string]bool  // "YYYY-MM-DD" local dates
    Increment     Increment
    SetupFee      money.Money      // charged once per answered call
    Tiers         []Tier
}

func LoadTieredPlan(r io.Reader) (*TieredPlan, error)
```

Tariff file format (JSON, money values are decimal strings, see README):

```json
{
  "code": "BIZ-TIER-2026",
  "timezone": "Europe/Madrid",
  "peak": {"start_hour": 8, "end_hour": 20},
  "holidays": ["2026-01-06", "2026-05-01"],
  "increment": "30/6",
  "setup_fee": "0.0150",
  "tiers": [
    {"up_to_minutes": 100, "peak": "0.0900", "off_peak": "0.0450"},
    {"up_to_minutes": 0,   "peak": "0.0600", "off_peak": "0.0300"}
  ]
}
```

`LoadTieredPlan` must return an error for: unknown JSON fields, missing `code`,
missing/unknown `timezone` (IANA name), missing `peak`, peak hours outside
0..24 or `start_hour >= end_hour`, an invalid `increment`, an invalid or
negative money value (rates or `setup_fee`), an invalid holiday date, no tiers,
a last tier that is not unlimited (`up_to_minutes` must be 0), or non-last tiers
whose `up_to_minutes` are not positive and strictly increasing.
`holidays` and `setup_fee` are optional (empty map / zero). In the loaded plan
`Tier.UpToSeconds = up_to_minutes * 60`.

### Rating

```go
type Segment struct { Tier int; Seconds int64 } // Tier = 0-based index into plan.Tiers

type Rated struct {
    Billable int64       // billable seconds after increments
    Band     string      // BandPeak or BandOffPeak
    Cycle    string      // billing cycle "YYYY-MM"
    Segments []Segment   // in tier order; only tiers with Seconds > 0
    Amount   money.Money
}

func NewTieredRater(p *TieredPlan) *TieredRater
func (r *TieredRater) Rate(rec cdr.Record) (Rated, error)
func (r *TieredRater) Usage(subscriber, cycle string) int64 // billable seconds recorded so far
```

Rules (all wall-clock rules use the **plan's time zone**, applied to `rec.Start`):

1. **Band** is determined by the call's start and applies to the whole call:
   peak if the local day is Monday–Friday, is not in `Holidays`, and the local
   hour is in `[PeakStartHour, PeakEndHour)`; otherwise off-peak.
2. **Cycle** is the local calendar month of the start (`"2026-04"`). Usage is
   tracked per `(rec.Subscriber, cycle)`; records are rated in the order given.
3. Unanswered calls or calls with duration 0: `Billable 0`, `Amount 0`, no
   segments, no setup fee, no usage recorded (`Band` and `Cycle` still set).
   A negative `DurationSec` is an error.
4. `Billable = plan.Increment.Billable(DurationSec)`. The billable seconds are
   allocated to tiers starting from the subscriber's current cycle usage: tier
   *i* covers cumulative usage up to `Tiers[i].UpToSeconds`; a call that crosses
   a threshold is split between tiers. The last tier takes the rest.
   Afterwards the subscriber's usage grows by `Billable`.
5. `Amount = SetupFee + round_half_up( Σ segment.Seconds × rate_of(tier, band) / 60 )`,
   in `money.Money` units — rounding happens **once per call** on the sum, not per segment.

Example (plan above): Tuesday 2026-03-10 09:15 Madrid, 125 s → band peak,
billable 126 s, amount `0.0150 + 126 × 0.0900 / 60 = 0.2040`.

## Acceptance criteria

- The API above exists with exactly these names and semantics.
- Existing flat-plan rating, money and CDR parsing behaviour is unchanged; `go test ./...` passes.

## Constraints

- Standard library only; no floats for money.
