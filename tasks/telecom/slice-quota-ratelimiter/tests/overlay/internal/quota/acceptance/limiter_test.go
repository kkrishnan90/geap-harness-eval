package acceptance

import (
	"errors"
	"sync"
	"testing"
	"time"

	"telco.example/pcf-quota/internal/clock"
	"telco.example/pcf-quota/internal/quota"
	"telco.example/pcf-quota/internal/snssai"
)

var (
	t0     = time.Date(2026, 6, 1, 8, 0, 0, 0, time.UTC)
	embb   = snssai.MustParse("1-000001")
	urllc  = snssai.MustParse("2-0000a1")
	unused = snssai.MustParse("4")
)

func spec(s snssai.SNSSAI, aggRate, aggBurst, subRate, subBurst int64) quota.SliceSpec {
	return quota.SliceSpec{
		Slice:         s,
		Aggregate:     quota.BucketSpec{RatePerSec: aggRate, Burst: aggBurst},
		PerSubscriber: quota.BucketSpec{RatePerSec: subRate, Burst: subBurst},
	}
}

func newLimiter(t *testing.T, specs ...quota.SliceSpec) (*quota.Limiter, *clock.Fake) {
	t.Helper()
	clk := clock.NewFake(t0)
	l, err := quota.NewLimiter(clk, specs)
	if err != nil {
		t.Fatalf("NewLimiter: %v", err)
	}
	return l, clk
}

func mustAllow(t *testing.T, l *quota.Limiter, s snssai.SNSSAI, supi string, n int64) {
	t.Helper()
	if d := l.Allow(s, supi, n); !d.Allowed || d.Reason != quota.ReasonOK {
		t.Fatalf("Allow(%s,%s,%d) = %+v, want allowed", s, supi, n, d)
	}
}

func avail(t *testing.T, l *quota.Limiter, s snssai.SNSSAI, supi string) (int64, int64) {
	t.Helper()
	sub, agg, ok := l.Available(s, supi)
	if !ok {
		t.Fatalf("Available(%s) not ok", s)
	}
	return sub, agg
}

func TestLimiterBucketsStartFull(t *testing.T) {
	l, _ := newLimiter(t, spec(embb, 1000, 1000, 10, 100))
	if sub, agg := avail(t, l, embb, "imsi-001010000000001"); sub != 100 || agg != 1000 {
		t.Fatalf("available = %d/%d, want 100/1000", sub, agg)
	}
	mustAllow(t, l, embb, "imsi-001010000000001", 100)
	d := l.Allow(embb, "imsi-001010000000001", 1)
	if d.Allowed || d.Reason != quota.ReasonSubscriberQuota || d.RetryAfter != 100*time.Millisecond {
		t.Fatalf("got %+v, want subscriber-quota retry 100ms", d)
	}
}

func TestLimiterManySmallStepsAccumulateExactly(t *testing.T) {
	l, clk := newLimiter(t, spec(embb, 1_000_000, 1_000_000, 7, 50))
	mustAllow(t, l, embb, "a", 50)
	admitted := 0
	for i := 1; i <= 1000; i++ {
		clk.Advance(time.Millisecond)
		if l.Allow(embb, "a", 1).Allowed {
			// at 7 tokens/s the k-th token is available after ceil(k*1000/7) ms
			if admitted == 0 && i != 143 {
				t.Fatalf("first token admitted after %d ms, want 143 ms", i)
			}
			admitted++
		}
	}
	if admitted != 7 {
		t.Fatalf("admitted %d tokens over 1s at 7/s, want exactly 7", admitted)
	}
}

func TestLimiterFractionalCarry(t *testing.T) {
	l, clk := newLimiter(t, spec(embb, 1000, 1000, 3, 10))
	mustAllow(t, l, embb, "a", 10)
	for i := 0; i < 3; i++ {
		clk.Advance(333_333_333 * time.Nanosecond)
		l.Available(embb, "a")
	}
	if sub, _ := avail(t, l, embb, "a"); sub != 2 {
		t.Fatalf("after 999999999ns at 3/s: %d tokens, want 2", sub)
	}
	clk.Advance(time.Nanosecond)
	if sub, _ := avail(t, l, embb, "a"); sub != 3 {
		t.Fatalf("after 1s at 3/s: %d tokens, want 3", sub)
	}
}

func TestLimiterRetryAfterUsesCarry(t *testing.T) {
	l, clk := newLimiter(t, spec(embb, 1000, 1000, 3, 10))
	mustAllow(t, l, embb, "a", 10)
	clk.Advance(100 * time.Millisecond) // 0.3 token accumulated
	d := l.Allow(embb, "a", 1)
	if d.Allowed || d.RetryAfter != 233_333_334*time.Nanosecond {
		t.Fatalf("got %+v, want retry 233333334ns", d)
	}
	clk.Advance(d.RetryAfter - time.Nanosecond)
	if l.Allow(embb, "a", 1).Allowed {
		t.Fatal("allowed 1ns before RetryAfter")
	}
	clk.Advance(time.Nanosecond)
	mustAllow(t, l, embb, "a", 1)
}

func TestLimiterRequestLargerThanBurst(t *testing.T) {
	l, _ := newLimiter(t, spec(embb, 1000, 150, 10, 200))
	d := l.Allow(embb, "a", 201)
	if d.Allowed || d.Reason != quota.ReasonSubscriberQuota || d.RetryAfter != 0 {
		t.Fatalf("n > subscriber burst: %+v", d)
	}
	d = l.Allow(embb, "a", 151)
	if d.Allowed || d.Reason != quota.ReasonSliceQuota || d.RetryAfter != 0 {
		t.Fatalf("n > aggregate burst: %+v", d)
	}
}

func TestLimiterAggregateSharedAcrossSubscribers(t *testing.T) {
	l, _ := newLimiter(t, spec(embb, 50, 250, 10, 100))
	mustAllow(t, l, embb, "a", 100)
	mustAllow(t, l, embb, "b", 100)
	d := l.Allow(embb, "c", 100)
	if d.Allowed || d.Reason != quota.ReasonSliceQuota || d.RetryAfter != time.Second {
		t.Fatalf("got %+v, want slice-quota retry 1s", d)
	}
	mustAllow(t, l, embb, "c", 50)
	if sub, agg := avail(t, l, embb, "c"); sub != 50 || agg != 0 {
		t.Fatalf("available c=%d agg=%d, want 50/0", sub, agg)
	}
}

func TestLimiterDeniedRequestTakesNothing(t *testing.T) {
	l, _ := newLimiter(t, spec(embb, 10, 130, 10, 100))
	mustAllow(t, l, embb, "a", 100)
	if d := l.Allow(embb, "b", 50); d.Allowed || d.Reason != quota.ReasonSliceQuota {
		t.Fatalf("got %+v", d)
	}
	if sub, agg := avail(t, l, embb, "b"); sub != 100 || agg != 30 {
		t.Fatalf("after denial b=%d agg=%d, want 100/30", sub, agg)
	}
	if d := l.Allow(embb, "a", 1); d.Allowed || d.Reason != quota.ReasonSubscriberQuota {
		t.Fatalf("got %+v", d)
	}
	if _, agg := avail(t, l, embb, "a"); agg != 30 {
		t.Fatalf("aggregate changed by a subscriber denial: %d", agg)
	}
}

func TestLimiterSlicesIsolated(t *testing.T) {
	l, _ := newLimiter(t, spec(embb, 10, 100, 10, 100), spec(urllc, 10, 100, 10, 100))
	mustAllow(t, l, embb, "a", 100)
	mustAllow(t, l, urllc, "a", 100)
	if _, agg := avail(t, l, urllc, "x"); agg != 0 {
		t.Fatalf("urllc agg = %d", agg)
	}
}

func TestLimiterUnknownSliceAndInvalidRequests(t *testing.T) {
	l, _ := newLimiter(t, spec(embb, 10, 100, 10, 100))
	if d := l.Allow(unused, "a", 1); d.Allowed || d.Reason != quota.ReasonUnknownSlice {
		t.Fatalf("unknown slice: %+v", d)
	}
	for _, n := range []int64{0, -5} {
		if d := l.Allow(embb, "a", n); d.Allowed || d.Reason != quota.ReasonInvalidRequest {
			t.Fatalf("n=%d: %+v", n, d)
		}
	}
	if d := l.Allow(embb, "", 1); d.Allowed || d.Reason != quota.ReasonInvalidRequest {
		t.Fatalf("empty supi: %+v", d)
	}
	if _, _, ok := l.Available(unused, "a"); ok {
		t.Fatal("Available on unknown slice reported ok")
	}
	if sub, agg := avail(t, l, embb, "a"); sub != 100 || agg != 100 {
		t.Fatalf("invalid requests consumed tokens: %d/%d", sub, agg)
	}
}

func TestLimiterClockStepBackwards(t *testing.T) {
	l, clk := newLimiter(t, spec(embb, 1000, 1000, 10, 100))
	mustAllow(t, l, embb, "a", 100)
	clk.Set(t0.Add(-10 * time.Second))
	if sub, _ := avail(t, l, embb, "a"); sub != 0 {
		t.Fatalf("tokens after backwards step: %d", sub)
	}
	clk.Set(t0.Add(time.Second))
	if sub, _ := avail(t, l, embb, "a"); sub != 10 {
		t.Fatalf("after recovering to t0+1s: %d tokens, want 10", sub)
	}
}

func TestLimiterLongIdleNoOverflow(t *testing.T) {
	big := int64(9_000_000_000_000_000_000)
	l, clk := newLimiter(t, spec(embb, 1_000_000_000_000, big, 1_000_000_000_000, big))
	mustAllow(t, l, embb, "a", big)
	clk.Advance(10 * 365 * 24 * time.Hour)
	if sub, agg := avail(t, l, embb, "a"); sub != big || agg != big {
		t.Fatalf("after 10y idle: %d/%d, want full", sub, agg)
	}
	mustAllow(t, l, embb, "a", big)
	clk.Advance(time.Second)
	if sub, _ := avail(t, l, embb, "a"); sub != 1_000_000_000_000 {
		t.Fatalf("after 1s at 1e12/s: %d", sub)
	}
}

func TestLimiterCarryDiscardedWhenFull(t *testing.T) {
	l, clk := newLimiter(t, spec(embb, 1000, 1000, 3, 5))
	mustAllow(t, l, embb, "a", 5)
	clk.Advance(10500 * time.Millisecond) // far more than needed to refill
	mustAllow(t, l, embb, "a", 1)
	clk.Advance(166_666_667 * time.Nanosecond) // 0.5 token
	if sub, _ := avail(t, l, embb, "a"); sub != 4 {
		t.Fatalf("got %d tokens, want 4 (fractional carry must reset when the bucket is full)", sub)
	}
}

func TestLimiterNewSubscriberStartsFullLater(t *testing.T) {
	l, clk := newLimiter(t, spec(embb, 1000, 1000, 10, 100))
	clk.Advance(time.Hour)
	mustAllow(t, l, embb, "late", 100)
	if sub, agg := avail(t, l, embb, "late"); sub != 0 || agg != 900 {
		t.Fatalf("got %d/%d", sub, agg)
	}
}

func TestLimiterRejectsInvalidSpecs(t *testing.T) {
	clk := clock.NewFake(t0)
	bad := []([]quota.SliceSpec){
		{spec(embb, 0, 10, 1, 1)},
		{spec(embb, 1, 10, 1, 0)},
		{spec(embb, 1, 10, 1, 1), spec(embb, 1, 10, 1, 1)},
	}
	for i, specs := range bad {
		if _, err := quota.NewLimiter(clk, specs); !errors.Is(err, quota.ErrInvalidSpec) {
			t.Errorf("case %d: err = %v, want ErrInvalidSpec", i, err)
		}
	}
}

func TestLimiterConcurrentAggregateExact(t *testing.T) {
	l, _ := newLimiter(t, spec(embb, 1, 1000, 1, 1_000_000))
	var wg sync.WaitGroup
	var mu sync.Mutex
	allowed := 0
	start := make(chan struct{})
	for g := 0; g < 40; g++ {
		wg.Add(1)
		go func(g int) {
			defer wg.Done()
			<-start
			local := 0
			for i := 0; i < 50; i++ {
				supi := string(rune('A'+g%26)) + string(rune('a'+i%26)) + string(rune('0'+g/26))
				if l.Allow(embb, supi, 1).Allowed {
					local++
				}
			}
			mu.Lock()
			allowed += local
			mu.Unlock()
		}(g)
	}
	close(start)
	wg.Wait()
	if allowed != 1000 {
		t.Fatalf("admitted %d, want exactly 1000", allowed)
	}
}

func TestLimiterConcurrentSingleSubscriberExact(t *testing.T) {
	l, _ := newLimiter(t, spec(embb, 1, 1_000_000, 1, 100), spec(urllc, 1, 1_000_000, 1, 100))
	var wg sync.WaitGroup
	var mu sync.Mutex
	allowed := map[snssai.SNSSAI]int{}
	start := make(chan struct{})
	for g := 0; g < 64; g++ {
		wg.Add(1)
		go func(g int) {
			defer wg.Done()
			<-start
			s := embb
			if g%2 == 1 {
				s = urllc
			}
			for i := 0; i < 10; i++ {
				if l.Allow(s, "imsi-001010000000042", 1).Allowed {
					mu.Lock()
					allowed[s]++
					mu.Unlock()
				}
			}
		}(g)
	}
	close(start)
	wg.Wait()
	if allowed[embb] != 100 || allowed[urllc] != 100 {
		t.Fatalf("admitted %v, want 100 per slice", allowed)
	}
}
