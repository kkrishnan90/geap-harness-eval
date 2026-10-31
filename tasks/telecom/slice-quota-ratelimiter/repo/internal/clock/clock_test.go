package clock

import (
	"testing"
	"time"
)

func TestFakeClockAdvance(t *testing.T) {
	t0 := time.Date(2026, 3, 1, 12, 0, 0, 0, time.UTC)
	f := NewFake(t0)
	f.Advance(1500 * time.Millisecond)
	if got := f.Now().Sub(t0); got != 1500*time.Millisecond {
		t.Fatalf("advanced %v", got)
	}
}

func TestFakeClockSetBackwards(t *testing.T) {
	t0 := time.Date(2026, 3, 1, 12, 0, 0, 0, time.UTC)
	f := NewFake(t0)
	f.Set(t0.Add(-time.Second))
	if !f.Now().Before(t0) {
		t.Fatal("expected earlier time")
	}
}
