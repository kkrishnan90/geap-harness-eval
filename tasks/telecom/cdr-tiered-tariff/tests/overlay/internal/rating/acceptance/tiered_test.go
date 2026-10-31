package acceptance

import (
	"reflect"
	"strings"
	"testing"
	"time"
	_ "time/tzdata"

	"github.com/telcoridge/mediation/internal/cdr"
	"github.com/telcoridge/mediation/internal/rating"
)

const bizPlan = `{
  "code": "BIZ-TIER-2026",
  "timezone": "Europe/Madrid",
  "peak": {"start_hour": 8, "end_hour": 20},
  "holidays": ["2026-01-06", "2026-05-01"],
  "increment": "30/6",
  "setup_fee": "0.0150",
  "tiers": [
    {"up_to_minutes": 100, "peak": "0.0900", "off_peak": "0.0450"},
    {"up_to_minutes": 0, "peak": "0.0600", "off_peak": "0.0300"}
  ]
}`

func mustPlan(t *testing.T, src string) *rating.TieredPlan {
	t.Helper()
	p, err := rating.LoadTieredPlan(strings.NewReader(src))
	if err != nil {
		t.Fatalf("LoadTieredPlan: %v", err)
	}
	return p
}

func utc(s string) time.Time {
	v, err := time.Parse(time.RFC3339, s)
	if err != nil {
		panic(err)
	}
	return v
}

func rec(sub, start string, secs int64) cdr.Record {
	return cdr.Record{ID: sub + "@" + start, Subscriber: sub, Called: "+34911222333",
		Start: utc(start), DurationSec: secs, Answered: secs > 0}
}

func rate(t *testing.T, r *rating.TieredRater, c cdr.Record) rating.Rated {
	t.Helper()
	out, err := r.Rate(c)
	if err != nil {
		t.Fatalf("Rate(%s): %v", c.ID, err)
	}
	return out
}

func expect(t *testing.T, got rating.Rated, band, amount string, billable int64) {
	t.Helper()
	if got.Band != band || got.Amount.String() != amount || got.Billable != billable {
		t.Errorf("got band=%s amount=%s billable=%d, want band=%s amount=%s billable=%d",
			got.Band, got.Amount, got.Billable, band, amount, billable)
	}
}

func TestTieredIncrementBillable(t *testing.T) {
	cases := []struct {
		inc  rating.Increment
		in   int64
		want int64
	}{
		{rating.Increment{Initial: 60, Subsequent: 60}, 0, 0},
		{rating.Increment{Initial: 60, Subsequent: 60}, 1, 60},
		{rating.Increment{Initial: 60, Subsequent: 60}, 60, 60},
		{rating.Increment{Initial: 60, Subsequent: 60}, 61, 120},
		{rating.Increment{Initial: 30, Subsequent: 6}, 5, 30},
		{rating.Increment{Initial: 30, Subsequent: 6}, 30, 30},
		{rating.Increment{Initial: 30, Subsequent: 6}, 31, 36},
		{rating.Increment{Initial: 30, Subsequent: 6}, 37, 42},
		{rating.Increment{Initial: 1, Subsequent: 1}, 17, 17},
		{rating.Increment{Initial: 60, Subsequent: 1}, 75, 75},
	}
	for _, c := range cases {
		if got := c.inc.Billable(c.in); got != c.want {
			t.Errorf("%+v.Billable(%d) = %d, want %d", c.inc, c.in, got, c.want)
		}
	}
}

func TestTieredParseIncrement(t *testing.T) {
	inc, err := rating.ParseIncrement("30/6")
	if err != nil || inc != (rating.Increment{Initial: 30, Subsequent: 6}) {
		t.Fatalf("ParseIncrement(30/6) = %+v, %v", inc, err)
	}
	for _, bad := range []string{"60", "0/1", "1/0", "a/b", "-1/1", "", "60/60/60"} {
		if _, err := rating.ParseIncrement(bad); err == nil {
			t.Errorf("ParseIncrement(%q): expected error", bad)
		}
	}
}

func TestTieredLoadPlan(t *testing.T) {
	p := mustPlan(t, bizPlan)
	if p.Code != "BIZ-TIER-2026" || p.Location.String() != "Europe/Madrid" {
		t.Errorf("code/location = %s/%s", p.Code, p.Location)
	}
	if p.PeakStartHour != 8 || p.PeakEndHour != 20 {
		t.Errorf("peak = %d-%d", p.PeakStartHour, p.PeakEndHour)
	}
	if p.Increment != (rating.Increment{Initial: 30, Subsequent: 6}) {
		t.Errorf("increment = %+v", p.Increment)
	}
	if p.SetupFee.String() != "0.0150" {
		t.Errorf("setup fee = %s", p.SetupFee)
	}
	if !p.Holidays["2026-05-01"] || p.Holidays["2026-05-02"] {
		t.Errorf("holidays = %v", p.Holidays)
	}
	if len(p.Tiers) != 2 || p.Tiers[0].UpToSeconds != 6000 || p.Tiers[1].UpToSeconds != 0 {
		t.Fatalf("tiers = %+v", p.Tiers)
	}
	if p.Tiers[0].Peak.String() != "0.0900" || p.Tiers[1].OffPeak.String() != "0.0300" {
		t.Errorf("tier rates = %+v", p.Tiers)
	}
}

func TestTieredLoadPlanValidation(t *testing.T) {
	mutate := map[string][2]string{
		"bad timezone":       {`"Europe/Madrid"`, `"Europe/Atlantis"`},
		"inverted peak":      {`"start_hour": 8, "end_hour": 20`, `"start_hour": 20, "end_hour": 8`},
		"peak past midnight": {`"end_hour": 20`, `"end_hour": 25`},
		"bad increment":      {`"30/6"`, `"60"`},
		"zero increment":     {`"30/6"`, `"0/6"`},
		"last tier limited":  {`"up_to_minutes": 0`, `"up_to_minutes": 500`},
		"middle tier open":   {`"up_to_minutes": 100`, `"up_to_minutes": 0`},
		"negative rate":      {`"peak": "0.0600"`, `"peak": "-0.0600"`},
		"bad money":          {`"off_peak": "0.0450"`, `"off_peak": "0.04505"`},
		"bad holiday":        {`"2026-05-01"`, `"2026-13-01"`},
		"unknown field":      {`"increment"`, `"rounding": "up", "increment"`},
		"bad setup fee":      {`"0.0150"`, `"abc"`},
	}
	for name, m := range mutate {
		src := strings.Replace(bizPlan, m[0], m[1], 1)
		if src == bizPlan {
			t.Fatalf("%s: mutation did not apply", name)
		}
		if _, err := rating.LoadTieredPlan(strings.NewReader(src)); err == nil {
			t.Errorf("%s: expected error", name)
		}
	}
	noTiers := `{"code":"X","timezone":"UTC","peak":{"start_hour":8,"end_hour":20},"increment":"1/1","tiers":[]}`
	if _, err := rating.LoadTieredPlan(strings.NewReader(noTiers)); err == nil {
		t.Error("no tiers: expected error")
	}
	decreasing := `{"code":"X","timezone":"UTC","peak":{"start_hour":8,"end_hour":20},"increment":"1/1","tiers":[
	  {"up_to_minutes":100,"peak":"1","off_peak":"1"},{"up_to_minutes":50,"peak":"1","off_peak":"1"},{"up_to_minutes":0,"peak":"1","off_peak":"1"}]}`
	if _, err := rating.LoadTieredPlan(strings.NewReader(decreasing)); err == nil {
		t.Error("decreasing tiers: expected error")
	}
	minimal := `{"code":"X","timezone":"UTC","peak":{"start_hour":0,"end_hour":24},"increment":"1/1","tiers":[{"up_to_minutes":0,"peak":"1","off_peak":"1"}]}`
	if p, err := rating.LoadTieredPlan(strings.NewReader(minimal)); err != nil || p.SetupFee != 0 || len(p.Holidays) != 0 {
		t.Errorf("minimal plan: %v %+v", err, p)
	}
}

func TestTieredPeakWeekday(t *testing.T) {
	r := rating.NewTieredRater(mustPlan(t, bizPlan))
	got := rate(t, r, rec("+34600000001", "2026-03-10T08:15:00Z", 125)) // Tue 09:15 CET
	expect(t, got, rating.BandPeak, "0.2040", 126)
	if got.Cycle != "2026-03" || !reflect.DeepEqual(got.Segments, []rating.Segment{{Tier: 0, Seconds: 126}}) {
		t.Errorf("cycle/segments = %s %+v", got.Cycle, got.Segments)
	}
}

func TestTieredBandUsesPlanTimezone(t *testing.T) {
	r := rating.NewTieredRater(mustPlan(t, bizPlan))
	expect(t, rate(t, r, rec("+34600000002", "2026-03-10T07:30:00Z", 60)), rating.BandPeak, "0.1050", 60)    // 08:30 local
	expect(t, rate(t, r, rec("+34600000002", "2026-03-10T06:59:59Z", 60)), rating.BandOffPeak, "0.0600", 60) // 07:59:59 local
	expect(t, rate(t, r, rec("+34600000002", "2026-03-10T18:59:59Z", 60)), rating.BandPeak, "0.1050", 60)    // 19:59:59 local
	expect(t, rate(t, r, rec("+34600000002", "2026-03-10T19:00:00Z", 60)), rating.BandOffPeak, "0.0600", 60) // 20:00 local
	expect(t, rate(t, r, rec("+34600000002", "2026-03-30T06:30:00Z", 60)), rating.BandPeak, "0.1050", 60)    // Mon 08:30 CEST
}

func TestTieredWeekendAndHolidayOffPeak(t *testing.T) {
	r := rating.NewTieredRater(mustPlan(t, bizPlan))
	expect(t, rate(t, r, rec("+34600000003", "2026-03-14T09:00:00Z", 60)), rating.BandOffPeak, "0.0600", 60) // Saturday
	expect(t, rate(t, r, rec("+34600000003", "2026-03-15T12:00:00Z", 60)), rating.BandOffPeak, "0.0600", 60) // Sunday
	expect(t, rate(t, r, rec("+34600000003", "2026-05-01T08:00:00Z", 60)), rating.BandOffPeak, "0.0600", 60) // Fri holiday 10:00 CEST
	expect(t, rate(t, r, rec("+34600000003", "2026-01-05T23:30:00Z", 60)), rating.BandOffPeak, "0.0600", 60) // 00:30 Jan 6 local (holiday)
	expect(t, rate(t, r, rec("+34600000003", "2026-01-06T23:30:00Z", 60)), rating.BandOffPeak, "0.0600", 60) // Jan 7 00:30, normal night
	expect(t, rate(t, r, rec("+34600000003", "2026-01-07T09:00:00Z", 60)), rating.BandPeak, "0.1050", 60)    // Jan 7 10:00
}

func TestTieredTierCrossingSplitsCall(t *testing.T) {
	r := rating.NewTieredRater(mustPlan(t, bizPlan))
	sub := "+34600000004"
	expect(t, rate(t, r, rec(sub, "2026-03-02T09:00:00Z", 5940)), rating.BandPeak, "8.9250", 5940)
	if u := r.Usage(sub, "2026-03"); u != 5940 {
		t.Fatalf("usage = %d", u)
	}
	got := rate(t, r, rec(sub, "2026-03-03T09:00:00Z", 120))
	expect(t, got, rating.BandPeak, "0.1650", 120)
	if !reflect.DeepEqual(got.Segments, []rating.Segment{{Tier: 0, Seconds: 60}, {Tier: 1, Seconds: 60}}) {
		t.Errorf("segments = %+v", got.Segments)
	}
	got = rate(t, r, rec(sub, "2026-03-07T09:00:00Z", 30)) // Saturday, fully in tier 1
	expect(t, got, rating.BandOffPeak, "0.0300", 30)
	if !reflect.DeepEqual(got.Segments, []rating.Segment{{Tier: 1, Seconds: 30}}) {
		t.Errorf("segments = %+v", got.Segments)
	}
	if u := r.Usage(sub, "2026-03"); u != 6090 {
		t.Errorf("usage = %d, want 6090", u)
	}
}

func TestTieredCycleIsLocalCalendarMonth(t *testing.T) {
	r := rating.NewTieredRater(mustPlan(t, bizPlan))
	sub := "+34600000005"
	rate(t, r, rec(sub, "2026-03-02T09:00:00Z", 6600)) // 110 min: into tier 1
	// 2026-03-31T22:30Z is 00:30 on 1 April in Madrid: new cycle, tier 0 again (Wed night, off-peak).
	got := rate(t, r, rec(sub, "2026-03-31T22:30:00Z", 60))
	expect(t, got, rating.BandOffPeak, "0.0600", 60)
	if got.Cycle != "2026-04" {
		t.Errorf("cycle = %s", got.Cycle)
	}
	if r.Usage(sub, "2026-03") != 6600 || r.Usage(sub, "2026-04") != 60 {
		t.Errorf("usage march=%d april=%d", r.Usage(sub, "2026-03"), r.Usage(sub, "2026-04"))
	}
}

func TestTieredUsageIsPerSubscriber(t *testing.T) {
	r := rating.NewTieredRater(mustPlan(t, bizPlan))
	rate(t, r, rec("+34600000006", "2026-03-02T09:00:00Z", 6600))
	expect(t, rate(t, r, rec("+34600000007", "2026-03-02T10:00:00Z", 60)), rating.BandPeak, "0.1050", 60)
	if r.Usage("+34600000007", "2026-03") != 60 || r.Usage("+34600000008", "2026-03") != 0 {
		t.Error("usage leaked between subscribers")
	}
}

func TestTieredUnansweredIsFree(t *testing.T) {
	r := rating.NewTieredRater(mustPlan(t, bizPlan))
	c := rec("+34600000009", "2026-03-10T08:15:00Z", 0)
	got := rate(t, r, c)
	if got.Amount != 0 || got.Billable != 0 || len(got.Segments) != 0 {
		t.Errorf("unanswered = %+v", got)
	}
	if r.Usage("+34600000009", "2026-03") != 0 {
		t.Error("unanswered call recorded usage")
	}
}

func TestTieredRoundsOncePerCall(t *testing.T) {
	plan := mustPlan(t, `{"code":"RND","timezone":"UTC","peak":{"start_hour":8,"end_hour":20},"increment":"1/1",
	  "tiers":[{"up_to_minutes":1,"peak":"0.0090","off_peak":"0.0090"},{"up_to_minutes":0,"peak":"0.0030","off_peak":"0.0030"}]}`)
	r := rating.NewTieredRater(plan)
	expect(t, rate(t, r, rec("+1", "2026-03-10T09:00:00Z", 59)), rating.BandPeak, "0.0089", 59)
	// 1 s at 0.0090/min (1.5 units) + 1 s at 0.0030/min (0.5 units) = 2 units, not 3.
	expect(t, rate(t, r, rec("+1", "2026-03-10T09:05:00Z", 2)), rating.BandPeak, "0.0002", 2)
}

func TestTieredPerMinuteIncrement(t *testing.T) {
	plan := mustPlan(t, strings.Replace(bizPlan, `"30/6"`, `"60/60"`, 1))
	r := rating.NewTieredRater(plan)
	// 61 s -> 120 billable at 0.0900 = 0.1800 + 0.0150
	expect(t, rate(t, r, rec("+34600000010", "2026-03-10T08:15:00Z", 61)), rating.BandPeak, "0.1950", 120)
}

func TestTieredRejectsNegativeDuration(t *testing.T) {
	r := rating.NewTieredRater(mustPlan(t, bizPlan))
	c := rec("+34600000011", "2026-03-10T08:15:00Z", 10)
	c.DurationSec = -5
	if _, err := r.Rate(c); err == nil {
		t.Error("expected error for negative duration")
	}
}
