package eta

import (
	"testing"
	"time"
)

// 2026 transitions: EU last Sunday of March / October = Mar 29 / Oct 25;
// US second Sunday of March / first Sunday of November = Mar 8 / Nov 1.

func TestDSTSpringForwardDriveEU(t *testing.T) {
	p := planner(t)
	dep := at(t, "Europe/Berlin", "2026-03-29 01:30") // CET, 00:30Z
	res, err := p.Estimate("HAM", dep, []Leg{{To: "BER", Drive: 2 * time.Hour}})
	if err != nil {
		t.Fatal(err)
	}
	wantTime(t, "ETA", res.ETA, time.Date(2026, 3, 29, 2, 30, 0, 0, time.UTC))
	if res.Transit != 2*time.Hour {
		t.Errorf("transit = %s, want 2h", res.Transit)
	}
	if got := res.ETA.Format("15:04 MST"); got != "04:30 CEST" {
		t.Errorf("local ETA = %s", got)
	}
}

func TestDSTFallBackDriveUS(t *testing.T) {
	p := planner(t)
	dep := at(t, "America/Denver", "2026-10-31 23:30") // MDT, Nov 1 05:30Z
	res, err := p.Estimate("DEN", dep, []Leg{{To: "CHI", Drive: 3 * time.Hour}})
	if err != nil {
		t.Fatal(err)
	}
	wantTime(t, "ETA", res.ETA, time.Date(2026, 11, 1, 8, 30, 0, 0, time.UTC))
	if res.Transit != 3*time.Hour {
		t.Errorf("transit = %s, want 3h", res.Transit)
	}
	if got := res.ETA.Format("15:04 MST"); got != "02:30 CST" {
		t.Errorf("local ETA = %s", got)
	}
}

func TestDSTBreakAcrossSpringForwardUS(t *testing.T) {
	p := planner(t)
	dep := at(t, "America/Chicago", "2026-03-07 22:00") // CST, Mar 8 04:00Z
	res, err := p.Estimate("CHI", dep, []Leg{{To: "ATL", Drive: 6 * time.Hour}})
	if err != nil {
		t.Fatal(err)
	}
	// 6h driving + 45m break = 6h45 elapsed.
	wantTime(t, "ETA", res.ETA, time.Date(2026, 3, 8, 10, 45, 0, 0, time.UTC))
	if res.Transit != 6*time.Hour+45*time.Minute {
		t.Errorf("transit = %s", res.Transit)
	}
}

func TestDSTReceivingWindowNextDaySpringForward(t *testing.T) {
	p := planner(t)
	dep := at(t, "America/New_York", "2026-03-07 21:10")
	res, err := p.Estimate("ATL", dep, []Leg{{To: "NYC", Drive: 2 * time.Hour}})
	if err != nil {
		t.Fatal(err)
	}
	wantTime(t, "arrival", res.Stops[0].Arrival, time.Date(2026, 3, 8, 4, 10, 0, 0, time.UTC))
	// Dock opens 06:00 local = 06:00 EDT on the 8th.
	wantTime(t, "ETA", res.ETA, time.Date(2026, 3, 8, 10, 0, 0, 0, time.UTC))
	if got := res.ETA.Format("2006-01-02 15:04 MST"); got != "2026-03-08 06:00 EDT" {
		t.Errorf("local ETA = %s", got)
	}
}

func TestDSTReceivingWindowNextDayFallBack(t *testing.T) {
	p := planner(t)
	dep := at(t, "Europe/London", "2026-10-24 21:00")
	res, err := p.Estimate("LON", dep, []Leg{{To: "LON", Drive: 2 * time.Hour}})
	if err != nil {
		t.Fatal(err)
	}
	wantTime(t, "ETA", res.ETA, time.Date(2026, 10, 25, 6, 0, 0, 0, time.UTC))
	if got := res.ETA.Format("2006-01-02 15:04 MST"); got != "2026-10-25 06:00 GMT" {
		t.Errorf("local ETA = %s", got)
	}
	wantTime(t, "depart", res.Stops[0].Depart, time.Date(2026, 10, 25, 6, 30, 0, 0, time.UTC))
}

func TestDSTReceivingWindowSameDaySpringForward(t *testing.T) {
	p := planner(t)
	dep := at(t, "America/New_York", "2026-03-08 00:30") // EST, 05:30Z
	res, err := p.Estimate("ATL", dep, []Leg{{To: "NYC", Drive: 2 * time.Hour}})
	if err != nil {
		t.Fatal(err)
	}
	wantTime(t, "arrival", res.Stops[0].Arrival, time.Date(2026, 3, 8, 7, 30, 0, 0, time.UTC))
	wantTime(t, "ETA", res.ETA, time.Date(2026, 3, 8, 10, 0, 0, 0, time.UTC))
}

func TestDSTMultiLegOvernightEU(t *testing.T) {
	p := planner(t)
	// Madrid -> Hamburg (wait for dock) -> Berlin across the October change.
	dep := at(t, "Europe/Madrid", "2026-10-24 16:00") // CEST, 14:00Z
	res, err := p.Estimate("MAD", dep, []Leg{
		{To: "HAM", Drive: 9 * time.Hour},
		{To: "BER", Drive: 3 * time.Hour},
	})
	if err != nil {
		t.Fatal(err)
	}
	// 9h driving + 1 break = 9h45 -> 23:45Z (Oct 24) = 01:45 CEST Oct 25 -> wait for 06:00 CET (05:00Z).
	wantTime(t, "HAM arrival", res.Stops[0].Arrival, time.Date(2026, 10, 24, 23, 45, 0, 0, time.UTC))
	wantTime(t, "HAM accepted", res.Stops[0].Accepted, time.Date(2026, 10, 25, 5, 0, 0, 0, time.UTC))
	// dwell 30 -> 05:30Z, +3h -> 08:30Z (BER 24/7).
	wantTime(t, "ETA", res.ETA, time.Date(2026, 10, 25, 8, 30, 0, 0, time.UTC))
	if res.Transit != 18*time.Hour+30*time.Minute {
		t.Errorf("transit = %s", res.Transit)
	}
}
