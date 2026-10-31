# PCF-2210: Enforce network-slice quotas on the admission path

**Component:** pcf-quota (`internal/quota`) · **Priority:** High · **Type:** Feature

## Context

Enterprise customers buy dedicated 5G network slices (S-NSSAI) with a
contracted aggregate throughput, and each subscriber (SUPI) inside a slice
has its own cap. Slice specs are already modelled and loaded
(`internal/quota/spec.go`, `internal/policy`), but nothing enforces them.
Add the limiter used by the user-plane admission path.

## Design

Hierarchical token buckets: each slice has one **aggregate** bucket shared by
all its subscribers (`SliceSpec.Aggregate`) and one bucket **per subscriber**
created from `SliceSpec.PerSubscriber`. A request for `n` tokens is admitted
only if **both** the subscriber bucket and the aggregate bucket hold at least
`n` tokens; then `n` is taken from both. A denied request takes nothing from
either bucket.

## API (add to package `quota`, e.g. `internal/quota/limiter.go`)

```go
type Reason int
const (
    ReasonOK Reason = iota
    ReasonSubscriberQuota
    ReasonSliceQuota
    ReasonUnknownSlice
    ReasonInvalidRequest
)

type Decision struct {
    Allowed    bool
    Reason     Reason
    RetryAfter time.Duration
}

func NewLimiter(clk clock.Clock, specs []SliceSpec) (*Limiter, error)
func (l *Limiter) Allow(slice snssai.SNSSAI, supi string, n int64) Decision
func (l *Limiter) Available(slice snssai.SNSSAI, supi string) (subscriber, aggregate int64, ok bool)
```

## Rules

1. `NewLimiter` validates with `ValidateAll`; invalid specs return an error
   wrapping `ErrInvalidSpec`. All time comes from `clk.Now()`.
2. Buckets start **full** (`Burst` tokens): aggregate buckets at
   `NewLimiter`, subscriber buckets when the subscriber is first seen by
   `Allow` (at that moment's time).
3. **Exact integer refill.** Every bucket keeps a fractional remainder
   ("carry") in token-nanoseconds. When `t` ns have elapsed since the bucket
   was last updated it gains `floor((carry + t * RatePerSec) / 1e9)` tokens and
   keeps the remainder as the new carry. Updating often or rarely must give the
   same result (e.g. at 7 tokens/s, 1000 updates 1 ms apart yield exactly 7
   tokens; the first one after 143 ms). Tokens never exceed `Burst`; when a
   bucket becomes full its carry is discarded (reset to 0). No floating point.
   No overflow for rates up to 1e12/s, bursts up to 9e18 and idle periods of
   years.
4. **Clock steps backwards:** if `now` is before the bucket's last update,
   add nothing and keep the last-update time unchanged (so the bucket resumes
   counting from that earlier reference once time passes it again).
5. `Allow` evaluation order (first match wins):
   1. `n <= 0` or empty `supi` -> `ReasonInvalidRequest`
   2. unknown slice -> `ReasonUnknownSlice`
   3. (refill both buckets to now)
   4. `n` > subscriber `Burst` -> `ReasonSubscriberQuota`, `RetryAfter` 0 (never possible)
   5. `n` > aggregate `Burst` -> `ReasonSliceQuota`, `RetryAfter` 0
   6. subscriber tokens < `n` -> `ReasonSubscriberQuota`
   7. aggregate tokens < `n` -> `ReasonSliceQuota`
   8. otherwise admitted (`Allowed: true`, `ReasonOK`).
6. **`RetryAfter`** for cases 6 and 7 is the *smallest* duration `d` after which
   that bucket (the one named by the reason) would hold `n` tokens, given its
   current tokens and carry: `ceil((need * 1e9 - carry) / RatePerSec)` ns with
   `need = n - tokens`. Example: 3 tokens/s, empty bucket, 100 ms elapsed ->
   retry after 233,333,334 ns. Zero when allowed.
7. `Available` refills to now and returns the subscriber's tokens (a full
   `PerSubscriber.Burst` for a subscriber never seen) and the slice aggregate
   tokens; `ok == false` for an unknown slice. It does not create subscribers.
8. `Limiter` is safe for concurrent use: with a frozen clock, N concurrent
   `Allow(…, 1)` calls against a bucket with B tokens admit exactly `min(N, B)`.
   Different slices must not contend on one global lock.

## Acceptance criteria

- The rules above hold; existing tests (`go test ./...`) stay green.
- Do not change `SliceSpec`, `BucketSpec`, `ValidateAll`, the `clock` or
  `snssai` packages' public API.

## Constraints

- Go 1.22, standard library only; never call `time.Now()` in `internal/quota`.
