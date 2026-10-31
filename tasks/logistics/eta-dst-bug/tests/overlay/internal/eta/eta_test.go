package eta

import (
	"errors"
	"testing"
	"time"

	"github.com/northline/fleetroute/internal/hubs"
)

func planner(t *testing.T) *Planner {
	t.Helper()
	reg, err := hubs.Parse(hubs.Default)
	if err != nil {
		t.Fatal(err)
	}
	return &Planner{Hubs: reg}
}

func at(t *testing.T, zone, s string) time.Time {
	t.Helper()
	loc, err := time.LoadLocation(zone)
	if err != nil {
		t.Fatal(err)
	}
	v, err := time.ParseInLocation("2006-01-02 15:04", s, loc)
	if err != nil {
		t.Fatal(err)
	}
	return v
}

func wantTime(t *testing.T, what string, got, want time.Time) {
	t.Helper()
	if !got.Equal(want) {
		t.Errorf("%s = %s, want %s", what, got.Format(time.RFC3339), want.Format(time.RFC3339))
	}
}

func TestSingleLegSummer(t *testing.T) {
	p := planner(t)
	dep := at(t, "Europe/Berlin", "2026-07-14 08:00")
	res, err := p.Estimate("HAM", dep, []Leg{{To: "BER", Drive: 3*time.Hour + 10*time.Minute}})
	if err != nil {
		t.Fatal(err)
	}
	wantTime(t, "ETA", res.ETA, at(t, "Europe/Berlin", "2026-07-14 11:10"))
	if res.Transit != 3*time.Hour+10*time.Minute {
		t.Errorf("transit = %s", res.Transit)
	}
	if res.ETA.Location().String() != "Europe/Berlin" {
		t.Errorf("ETA not in hub zone: %s", res.ETA.Location())
	}
}

func TestStatutoryBreak(t *testing.T) {
	p := planner(t)
	dep := at(t, "America/Chicago", "2026-06-02 20:00")
	// 6h driving => one 45 min break after 4h30.
	res, err := p.Estimate("CHI", dep, []Leg{{To: "ATL", Drive: 6 * time.Hour}})
	if err != nil {
		t.Fatal(err)
	}
	// 20:00 CDT + 6h45 = 02:45 CDT = 03:45 EDT
	wantTime(t, "ETA", res.ETA, at(t, "America/New_York", "2026-06-03 03:45"))
}

func TestWaitForReceivingWindowSameDay(t *testing.T) {
	p := planner(t)
	dep := at(t, "America/New_York", "2026-05-12 00:30")
	res, err := p.Estimate("ATL", dep, []Leg{{To: "NYC", Drive: 2 * time.Hour}})
	if err != nil {
		t.Fatal(err)
	}
	wantTime(t, "arrival", res.Stops[0].Arrival, at(t, "America/New_York", "2026-05-12 02:30"))
	wantTime(t, "ETA", res.ETA, at(t, "America/New_York", "2026-05-12 06:00"))
}

func TestWaitForReceivingWindowNextDay(t *testing.T) {
	p := planner(t)
	dep := at(t, "Europe/London", "2026-08-20 20:15")
	res, err := p.Estimate("LON", dep, []Leg{{To: "LON", Drive: 2 * time.Hour}})
	if err != nil {
		t.Fatal(err)
	}
	wantTime(t, "ETA", res.ETA, at(t, "Europe/London", "2026-08-21 06:00"))
}

func TestMultiLegWithDwell(t *testing.T) {
	p := planner(t)
	dep := at(t, "America/Denver", "2026-09-09 05:00")
	res, err := p.Estimate("DEN", dep, []Leg{
		{To: "CHI", Drive: 4 * time.Hour},
		{To: "ATL", Drive: 3 * time.Hour},
	})
	if err != nil {
		t.Fatal(err)
	}
	// CHI: 05:00 MDT + 4h = 09:00 MDT = 10:00 CDT; dwell 45 => depart 10:45 CDT (break reset).
	wantTime(t, "CHI depart", res.Stops[0].Depart, at(t, "America/Chicago", "2026-09-09 10:45"))
	// ATL: 10:45 CDT + 3h = 13:45 CDT = 14:45 EDT
	wantTime(t, "ETA", res.ETA, at(t, "America/New_York", "2026-09-09 14:45"))
	if res.Transit != 7*time.Hour+45*time.Minute {
		t.Errorf("transit = %s", res.Transit)
	}
}

func TestUnknownHub(t *testing.T) {
	p := planner(t)
	_, err := p.Estimate("CHI", time.Now(), []Leg{{To: "XXX", Drive: time.Hour}})
	if !errors.Is(err, ErrUnknownHub) {
		t.Fatalf("err = %v", err)
	}
}

func TestRejectsEmptyRoute(t *testing.T) {
	if _, err := planner(t).Estimate("CHI", time.Now(), nil); err == nil {
		t.Fatal("expected error")
	}
}
