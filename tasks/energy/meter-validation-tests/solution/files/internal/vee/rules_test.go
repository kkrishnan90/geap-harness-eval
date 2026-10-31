package vee

import (
	"reflect"
	"testing"
	"time"

	"grid.example/mdm/internal/interval"
)

var day = time.Date(2026, 2, 9, 0, 0, 0, 0, time.UTC)

func slot(i int) time.Time { return day.Add(time.Duration(i) * 15 * time.Minute) }

func rd(i int, wh int64) interval.Reading {
	return interval.Reading{MeterID: "M-0042", Start: slot(i), Wh: wh}
}

// series builds readings for slots [0, n) with the given values; values < -1e9 mean "missing".
const missing = int64(-1 << 62)

func series(values ...int64) []interval.Reading {
	var rs []interval.Reading
	for i, v := range values {
		if v != missing {
			rs = append(rs, rd(i, v))
		}
	}
	return rs
}

func codes(issues []Issue) []string {
	var out []string
	for _, is := range issues {
		out = append(out, string(is.Code)+"@"+is.Start.Format("15:04"))
	}
	return out
}

func check(t *testing.T, got []Issue, want ...string) {
	t.Helper()
	g := codes(got)
	if len(want) == 0 && len(g) == 0 {
		return
	}
	if !reflect.DeepEqual(g, want) {
		t.Fatalf("issues = %v, want %v", g, want)
	}
}

func TestRulesMisalignedIgnoredByOtherRules(t *testing.T) {
	rs := series(10, missing, 10, 10)
	rs = append(rs, interval.Reading{Start: slot(1).Add(7 * time.Minute), Wh: -5})
	check(t, Validate(rs, day, slot(4), DefaultConfig()), "GAP@00:15", "MISALIGNED@00:22")
}

func TestRulesDuplicateKeepsFirst(t *testing.T) {
	rs := append(series(10, 20, 30, 40), rd(1, 99_999))
	check(t, Validate(rs, day, slot(4), DefaultConfig()), "DUPLICATE@00:15")
}

func TestRulesSameStartSortedByCode(t *testing.T) {
	rs := append(series(10, 30_000, 30, 40), rd(1, 5))
	check(t, Validate(rs, day, slot(4), DefaultConfig()), "DUPLICATE@00:15", "HIGH@00:15")
}

func TestRulesNegative(t *testing.T) {
	check(t, Validate(series(10, -1, 30, 0), day, slot(4), DefaultConfig()), "NEGATIVE@00:15")
}

func TestRulesHighIsStrict(t *testing.T) {
	cfg := DefaultConfig()
	check(t, Validate(series(cfg.MaxWh, 1, cfg.MaxWh+1, 2), day, slot(4), cfg), "HIGH@00:30")
}

func TestRulesGapsAtBothEdges(t *testing.T) {
	check(t, Validate(series(missing, 10, 20, missing), day, slot(4), DefaultConfig()), "GAP@00:00", "GAP@00:45")
}

func TestRulesReadingsOutsideWindowIgnored(t *testing.T) {
	rs := series(10, 20, 30, 40, -7, 99_999)
	check(t, Validate(rs, day, slot(4), DefaultConfig()))
}

func TestRulesFlatlineAtExactCount(t *testing.T) {
	cfg := DefaultConfig()
	vals := []int64{5, 7, 7, 7, 7, 7, 7, 7, 7, 9}
	check(t, Validate(series(vals...), day, slot(len(vals)), cfg), "FLATLINE@00:15")
}

func TestRulesFlatlineOneShortIsFine(t *testing.T) {
	vals := []int64{5, 7, 7, 7, 7, 7, 7, 7, 9}
	check(t, Validate(series(vals...), day, slot(len(vals)), DefaultConfig()))
}

func TestRulesFlatlineReportedOnce(t *testing.T) {
	vals := make([]int64, 20)
	for i := range vals {
		vals[i] = 42
	}
	check(t, Validate(series(vals...), day, slot(20), DefaultConfig()), "FLATLINE@00:00")
}

func TestRulesZerosNeverFlatline(t *testing.T) {
	vals := make([]int64, 16)
	check(t, Validate(series(vals...), day, slot(16), DefaultConfig()))
}

func TestRulesFlatlineBrokenByGap(t *testing.T) {
	vals := []int64{7, 7, 7, 7, 7, missing, 7, 7, 7, 7}
	check(t, Validate(series(vals...), day, slot(len(vals)), DefaultConfig()), "GAP@01:15")
}

func estimates(rs []interval.Reading) []int64 {
	var out []int64
	for _, r := range rs {
		out = append(out, r.Wh)
	}
	return out
}

func TestEstimateRoundsHalfUp(t *testing.T) {
	est := Estimate(series(100, missing, 105), day, slot(3), DefaultConfig())
	if got := estimates(est); !reflect.DeepEqual(got, []int64{103}) {
		t.Fatalf("got %v, want [103]", got)
	}
	if est[0].Flags&interval.FlagEstimated == 0 || !est[0].Start.Equal(slot(1)) {
		t.Fatalf("bad estimate %+v", est[0])
	}
	est = Estimate(series(0, missing, missing, missing, 10), day, slot(5), DefaultConfig())
	if got := estimates(est); !reflect.DeepEqual(got, []int64{3, 5, 8}) {
		t.Fatalf("got %v, want [3 5 8]", got)
	}
}

func TestEstimateMaxGapLength(t *testing.T) {
	cfg := DefaultConfig()
	four := series(10, missing, missing, missing, missing, 60)
	if got := estimates(Estimate(four, day, slot(6), cfg)); !reflect.DeepEqual(got, []int64{20, 30, 40, 50}) {
		t.Fatalf("4-slot gap: got %v", got)
	}
	five := series(10, missing, missing, missing, missing, missing, 70)
	if got := Estimate(five, day, slot(7), cfg); len(got) != 0 {
		t.Fatalf("5-slot gap must not be estimated, got %v", estimates(got))
	}
}

func TestEstimateNeedsUsableNeighbours(t *testing.T) {
	cfg := DefaultConfig()
	if got := Estimate(series(missing, 10, missing), day, slot(3), cfg); len(got) != 0 {
		t.Fatalf("edge gaps must not be estimated, got %v", estimates(got))
	}
	if got := Estimate(series(10, missing, cfg.MaxWh+1), day, slot(3), cfg); len(got) != 0 {
		t.Fatalf("gap next to HIGH must not be estimated, got %v", estimates(got))
	}
}
