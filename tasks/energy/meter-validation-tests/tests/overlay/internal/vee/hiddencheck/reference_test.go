package hiddencheck

import (
	"testing"
	"time"

	"grid.example/mdm/internal/interval"
	"grid.example/mdm/internal/vee"
)

func TestHiddenReferenceMixedDay(t *testing.T) {
	cfg := vee.DefaultConfig()
	from := time.Date(2026, 2, 10, 0, 0, 0, 0, time.UTC)
	var rs []interval.Reading
	for i := 0; i < 96; i++ {
		if i == 40 || i == 41 {
			continue
		}
		rs = append(rs, interval.Reading{MeterID: "M9", Start: from.Add(time.Duration(i) * cfg.Interval), Wh: int64(200 + i)})
	}
	issues := vee.Validate(rs, from, from.Add(24*time.Hour), cfg)
	if len(issues) != 2 || issues[0].Code != vee.CodeGap {
		t.Fatalf("got %v", issues)
	}
	est := vee.Estimate(rs, from, from.Add(24*time.Hour), cfg)
	if len(est) != 2 || est[0].Wh != 240 || est[1].Wh != 241 {
		t.Fatalf("got %+v", est)
	}
}
