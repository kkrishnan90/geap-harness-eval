package vee

import (
	"testing"
	"time"

	"grid.example/mdm/internal/interval"
)

func TestVeeCleanDayHasNoIssues(t *testing.T) {
	cfg := DefaultConfig()
	from := time.Date(2026, 1, 5, 0, 0, 0, 0, time.UTC)
	to := from.Add(24 * time.Hour)
	var rs []interval.Reading
	for i, t0 := 0, from; t0.Before(to); i, t0 = i+1, t0.Add(cfg.Interval) {
		rs = append(rs, interval.Reading{MeterID: "M1", Start: t0, Wh: int64(100 + i%7)})
	}
	if issues := Validate(rs, from, to, cfg); len(issues) != 0 {
		t.Fatalf("unexpected issues: %v", issues)
	}
	if est := Estimate(rs, from, to, cfg); len(est) != 0 {
		t.Fatalf("unexpected estimates: %v", est)
	}
}
