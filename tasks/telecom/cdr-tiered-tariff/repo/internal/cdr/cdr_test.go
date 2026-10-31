package cdr

import (
	"strings"
	"testing"
	"time"
)

const sample = `id,subscriber,called,start,duration_sec,answered
c1,+34911000001,+34600111222,2026-03-10T08:15:00Z,125,true
c2,+34911000001,+33140000000,2026-03-10T09:00:00+01:00,0,false
`

func TestCDRParseCSV(t *testing.T) {
	recs, err := ParseCSV(strings.NewReader(sample))
	if err != nil {
		t.Fatal(err)
	}
	if len(recs) != 2 {
		t.Fatalf("got %d records", len(recs))
	}
	if recs[0].DurationSec != 125 || !recs[0].Answered || recs[0].Called != "+34600111222" {
		t.Errorf("rec0 = %+v", recs[0])
	}
	if !recs[1].Start.Equal(time.Date(2026, 3, 10, 8, 0, 0, 0, time.UTC)) {
		t.Errorf("rec1 start = %s", recs[1].Start)
	}
}

func TestCDRParseErrors(t *testing.T) {
	bad := []string{
		"id,who\n",
		"id,subscriber,called,start,duration_sec,answered\nx,a,b,notatime,1,true\n",
		"id,subscriber,called,start,duration_sec,answered\nx,a,b,2026-01-01T00:00:00Z,-1,true\n",
		"id,subscriber,called,start,duration_sec,answered\nx,a,b,2026-01-01T00:00:00Z,10,false\n",
	}
	for i, src := range bad {
		if _, err := ParseCSV(strings.NewReader(src)); err == nil {
			t.Errorf("case %d: expected error", i)
		}
	}
}
