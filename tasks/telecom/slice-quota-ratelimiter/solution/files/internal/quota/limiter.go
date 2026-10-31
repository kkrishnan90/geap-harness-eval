package quota

import (
	"fmt"
	"math"
	"math/bits"
	"sync"
	"time"

	"telco.example/pcf-quota/internal/clock"
	"telco.example/pcf-quota/internal/snssai"
)

const nanosPerSec = uint64(time.Second)

// Reason explains a Decision.
type Reason int

// Decision reasons.
const (
	ReasonOK Reason = iota
	ReasonSubscriberQuota
	ReasonSliceQuota
	ReasonUnknownSlice
	ReasonInvalidRequest
)

func (r Reason) String() string {
	switch r {
	case ReasonOK:
		return "ok"
	case ReasonSubscriberQuota:
		return "subscriber-quota"
	case ReasonSliceQuota:
		return "slice-quota"
	case ReasonUnknownSlice:
		return "unknown-slice"
	case ReasonInvalidRequest:
		return "invalid-request"
	}
	return fmt.Sprintf("reason(%d)", int(r))
}

// Decision is the outcome of Allow.
type Decision struct {
	Allowed    bool
	Reason     Reason
	RetryAfter time.Duration
}

// bucket is an exact integer token bucket. carry holds fractional tokens in
// units of token-nanoseconds (always < 1e9).
type bucket struct {
	spec   BucketSpec
	tokens int64
	carry  uint64
	last   time.Time
}

func newBucket(spec BucketSpec, now time.Time) *bucket {
	return &bucket{spec: spec, tokens: spec.Burst, last: now}
}

func (b *bucket) refill(now time.Time) {
	d := now.Sub(b.last)
	if d <= 0 {
		return // clock went backwards or did not move: keep the reference point
	}
	b.last = now
	if b.tokens >= b.spec.Burst {
		b.tokens, b.carry = b.spec.Burst, 0
		return
	}
	missing := b.spec.Burst - b.tokens
	if int64(d/time.Second) >= missing/b.spec.RatePerSec+1 {
		b.tokens, b.carry = b.spec.Burst, 0
		return
	}
	hi, lo := bits.Mul64(uint64(d), uint64(b.spec.RatePerSec))
	var c uint64
	lo, c = bits.Add64(lo, b.carry, 0)
	hi += c
	q, r := bits.Div64(hi, lo, nanosPerSec)
	if q >= uint64(missing) {
		b.tokens, b.carry = b.spec.Burst, 0
		return
	}
	b.tokens += int64(q)
	b.carry = r
}

// retryAfter is the smallest wait after which the bucket holds n tokens.
func (b *bucket) retryAfter(n int64) time.Duration {
	need := n - b.tokens
	if need <= 0 {
		return 0
	}
	hi, lo := bits.Mul64(uint64(need), nanosPerSec)
	var br uint64
	lo, br = bits.Sub64(lo, b.carry, 0)
	hi -= br
	rate := uint64(b.spec.RatePerSec)
	lo, c := bits.Add64(lo, rate-1, 0)
	hi += c
	if hi >= rate {
		return time.Duration(math.MaxInt64)
	}
	q, _ := bits.Div64(hi, lo, rate)
	if q > math.MaxInt64 {
		return time.Duration(math.MaxInt64)
	}
	return time.Duration(q)
}

type sliceState struct {
	spec SliceSpec
	mu   sync.Mutex
	agg  *bucket
	subs map[string]*bucket
}

// Limiter enforces hierarchical slice quotas. Safe for concurrent use.
type Limiter struct {
	clk    clock.Clock
	slices map[snssai.SNSSAI]*sliceState
}

// NewLimiter validates specs and returns a limiter whose buckets start full.
func NewLimiter(clk clock.Clock, specs []SliceSpec) (*Limiter, error) {
	if clk == nil {
		return nil, fmt.Errorf("%w: nil clock", ErrInvalidSpec)
	}
	if err := ValidateAll(specs); err != nil {
		return nil, err
	}
	now := clk.Now()
	l := &Limiter{clk: clk, slices: make(map[snssai.SNSSAI]*sliceState, len(specs))}
	for _, s := range specs {
		l.slices[s.Slice] = &sliceState{spec: s, agg: newBucket(s.Aggregate, now), subs: make(map[string]*bucket)}
	}
	return l, nil
}

// Allow tries to take n tokens from the subscriber's bucket and the slice's
// aggregate bucket atomically.
func (l *Limiter) Allow(slice snssai.SNSSAI, supi string, n int64) Decision {
	if n <= 0 || supi == "" {
		return Decision{Reason: ReasonInvalidRequest}
	}
	st, ok := l.slices[slice]
	if !ok {
		return Decision{Reason: ReasonUnknownSlice}
	}
	st.mu.Lock()
	defer st.mu.Unlock()
	now := l.clk.Now()
	sub, ok := st.subs[supi]
	if !ok {
		sub = newBucket(st.spec.PerSubscriber, now)
		st.subs[supi] = sub
	}
	sub.refill(now)
	st.agg.refill(now)
	switch {
	case n > sub.spec.Burst:
		return Decision{Reason: ReasonSubscriberQuota}
	case n > st.agg.spec.Burst:
		return Decision{Reason: ReasonSliceQuota}
	case sub.tokens < n:
		return Decision{Reason: ReasonSubscriberQuota, RetryAfter: sub.retryAfter(n)}
	case st.agg.tokens < n:
		return Decision{Reason: ReasonSliceQuota, RetryAfter: st.agg.retryAfter(n)}
	}
	sub.tokens -= n
	st.agg.tokens -= n
	return Decision{Allowed: true, Reason: ReasonOK}
}

// Available reports the tokens currently available to supi and to the slice
// aggregate (refilled to now). Unknown subscribers report a full bucket.
func (l *Limiter) Available(slice snssai.SNSSAI, supi string) (subscriber, aggregate int64, ok bool) {
	st, found := l.slices[slice]
	if !found {
		return 0, 0, false
	}
	st.mu.Lock()
	defer st.mu.Unlock()
	now := l.clk.Now()
	st.agg.refill(now)
	subscriber = st.spec.PerSubscriber.Burst
	if sub, ok := st.subs[supi]; ok {
		sub.refill(now)
		subscriber = sub.tokens
	}
	return subscriber, st.agg.tokens, true
}
