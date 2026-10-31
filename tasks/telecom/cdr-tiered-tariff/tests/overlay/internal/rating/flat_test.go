package rating

import (
	"errors"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/telcoridge/mediation/internal/cdr"
)

func loadFlat(t *testing.T) *FlatPlan {
	t.Helper()
	f, err := os.Open("../../testdata/flat.json")
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	p, err := LoadFlatPlan(f)
	if err != nil {
		t.Fatal(err)
	}
	return p
}

func call(called string, secs int64) cdr.Record {
	return cdr.Record{ID: "x", Subscriber: "+34911000001", Called: called,
		Start: time.Date(2026, 3, 10, 9, 0, 0, 0, time.UTC), DurationSec: secs, Answered: secs > 0}
}

func TestFlatRatesPerSecond(t *testing.T) {
	p := loadFlat(t)
	cases := []struct {
		called string
		secs   int64
		want   string
	}{
		{"+34911234567", 61, "0.0356"},
		{"+34600111222", 30, "0.0350"},
		{"+33140000000", 90, "0.1800"},
		{"+4930123456", 1, "0.0020"},
		{"+34911234567", 0, "0.0000"},
	}
	for _, c := range cases {
		got, err := RateFlat(call(c.called, c.secs), p)
		if err != nil {
			t.Fatal(err)
		}
		if got.String() != c.want {
			t.Errorf("%s %ds = %s, want %s", c.called, c.secs, got, c.want)
		}
	}
}

func TestFlatUnknownZone(t *testing.T) {
	_, err := RateFlat(call("+1212555", 10), loadFlat(t))
	if !errors.Is(err, ErrNoZone) {
		t.Fatalf("err = %v", err)
	}
}

func TestFlatPlanValidation(t *testing.T) {
	for _, src := range []string{`{"code":"x","zones":[]}`, `{"code":"x","zones":[{"name":"a","prefix":"1","rate_per_minute":"-1"}]}`, `{"code":"x","bogus":1}`} {
		if _, err := LoadFlatPlan(strings.NewReader(src)); err == nil {
			t.Errorf("expected error for %s", src)
		}
	}
}

func TestZoneLongestPrefix(t *testing.T) {
	zt := NewZoneTable([]Zone{{"national", "34"}, {"mobile", "346"}, {"mobile-mvno", "3460"}})
	for num, want := range map[string]string{"+34911": "national", "+346111": "mobile", "+34600": "mobile-mvno"} {
		z, ok := zt.Lookup(num)
		if !ok || z.Name != want {
			t.Errorf("%s -> %v %v, want %s", num, z, ok, want)
		}
	}
	if _, ok := zt.Lookup("+1"); ok {
		t.Error("expected no zone")
	}
}
