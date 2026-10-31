package interval

import (
	"strings"
	"testing"
)

func TestIntervalDecodeCSV(t *testing.T) {
	rs, err := DecodeCSV(strings.NewReader("meter_id,start,wh\nM1,2026-01-05T00:00:00Z,120\nM1,2026-01-05T00:15:00+01:00,80,1\n"))
	if err != nil {
		t.Fatal(err)
	}
	if len(rs) != 2 || rs[1].Start.Hour() != 23 || rs[1].Flags != FlagEstimated {
		t.Fatalf("got %+v", rs)
	}
	if TotalWh(rs) != 200 {
		t.Fatalf("total %d", TotalWh(rs))
	}
}

func TestIntervalDecodeCSVErrors(t *testing.T) {
	for _, in := range []string{"M1,notatime,1\n", "M1,2026-01-05T00:00:00Z,x\n", "M1,2026-01-05T00:00:00Z\n"} {
		if _, err := DecodeCSV(strings.NewReader(in)); err == nil {
			t.Errorf("%q: expected error", in)
		}
	}
}
