package rating

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"time"

	"github.com/telcoridge/mediation/internal/cdr"
	"github.com/telcoridge/mediation/internal/money"
)

// Band names reported on rated calls.
const (
	BandPeak    = "peak"
	BandOffPeak = "offpeak"
)

// Tier is one usage tier of a TieredPlan. UpToSeconds is the cumulative billable usage
// (seconds in the subscriber's billing cycle) up to which this tier applies; 0 on the
// last tier means unlimited.
type Tier struct {
	UpToSeconds int64
	Peak        money.Money // per minute
	OffPeak     money.Money // per minute
}

// TieredPlan prices calls by time band (peak/off-peak) and cumulative monthly usage tier.
type TieredPlan struct {
	Code          string
	Location      *time.Location
	PeakStartHour int // local hour, inclusive
	PeakEndHour   int // local hour, exclusive
	Holidays      map[string]bool
	Increment     Increment
	SetupFee      money.Money
	Tiers         []Tier
}

// Segment is the part of a call's billable seconds rated in one tier (0-based index).
type Segment struct {
	Tier    int
	Seconds int64
}

// Rated is the outcome of rating one call against a TieredPlan.
type Rated struct {
	Billable int64
	Band     string
	Cycle    string // "YYYY-MM" in the plan's time zone
	Segments []Segment
	Amount   money.Money
}

// TieredRater rates CDRs in order and tracks per-subscriber usage per billing cycle.
type TieredRater struct {
	plan  *TieredPlan
	usage map[string]int64
}

// NewTieredRater returns a rater with no recorded usage.
func NewTieredRater(p *TieredPlan) *TieredRater {
	return &TieredRater{plan: p, usage: map[string]int64{}}
}

func usageKey(subscriber, cycle string) string { return subscriber + "|" + cycle }

// Usage returns billable seconds recorded for a subscriber in a cycle ("YYYY-MM").
func (r *TieredRater) Usage(subscriber, cycle string) int64 {
	return r.usage[usageKey(subscriber, cycle)]
}

// Band returns the time band in which a call starting at t is rated.
func (p *TieredPlan) Band(t time.Time) string {
	local := t.In(p.Location)
	if local.Weekday() == time.Saturday || local.Weekday() == time.Sunday {
		return BandOffPeak
	}
	if p.Holidays[local.Format("2006-01-02")] {
		return BandOffPeak
	}
	if h := local.Hour(); h >= p.PeakStartHour && h < p.PeakEndHour {
		return BandPeak
	}
	return BandOffPeak
}

// Rate prices one record and records its usage.
func (r *TieredRater) Rate(rec cdr.Record) (Rated, error) {
	if rec.DurationSec < 0 {
		return Rated{}, fmt.Errorf("rating: %s: negative duration", rec.ID)
	}
	p := r.plan
	local := rec.Start.In(p.Location)
	out := Rated{Band: p.Band(rec.Start), Cycle: local.Format("2006-01")}
	if !rec.Answered || rec.DurationSec == 0 {
		return out, nil
	}
	out.Billable = p.Increment.Billable(rec.DurationSec)
	key := usageKey(rec.Subscriber, out.Cycle)
	used := r.usage[key]
	remaining := out.Billable
	var num int64 // money units * seconds
	var lower int64
	for i, tier := range p.Tiers {
		if remaining == 0 {
			break
		}
		last := i == len(p.Tiers)-1
		capacity := remaining
		if !last {
			start := used
			if start < lower {
				start = lower
			}
			capacity = tier.UpToSeconds - start
			if capacity < 0 {
				capacity = 0
			}
			if capacity > remaining {
				capacity = remaining
			}
		}
		if capacity > 0 {
			rate := tier.OffPeak
			if out.Band == BandPeak {
				rate = tier.Peak
			}
			num += int64(rate) * capacity
			out.Segments = append(out.Segments, Segment{Tier: i, Seconds: capacity})
			remaining -= capacity
			used += capacity
		}
		lower = tier.UpToSeconds
	}
	r.usage[key] = used
	out.Amount = p.SetupFee + money.Money(money.DivRoundHalfUp(num, 60))
	return out, nil
}

type tieredFile struct {
	Code     string `json:"code"`
	Timezone string `json:"timezone"`
	Peak     *struct {
		StartHour int `json:"start_hour"`
		EndHour   int `json:"end_hour"`
	} `json:"peak"`
	Holidays  []string `json:"holidays"`
	Increment string   `json:"increment"`
	SetupFee  string   `json:"setup_fee"`
	Tiers     []struct {
		UpToMinutes int64  `json:"up_to_minutes"`
		Peak        string `json:"peak"`
		OffPeak     string `json:"off_peak"`
	} `json:"tiers"`
}

// LoadTieredPlan reads and validates a tiered tariff file.
func LoadTieredPlan(r io.Reader) (*TieredPlan, error) {
	var f tieredFile
	dec := json.NewDecoder(r)
	dec.DisallowUnknownFields()
	if err := dec.Decode(&f); err != nil {
		return nil, fmt.Errorf("rating: tiered plan: %w", err)
	}
	bad := func(format string, a ...any) (*TieredPlan, error) {
		return nil, fmt.Errorf("rating: tiered plan %s: %s", f.Code, fmt.Sprintf(format, a...))
	}
	if f.Code == "" {
		return nil, errors.New("rating: tiered plan: code is required")
	}
	if f.Timezone == "" {
		return bad("timezone is required")
	}
	loc, err := time.LoadLocation(f.Timezone)
	if err != nil {
		return bad("timezone: %v", err)
	}
	if f.Peak == nil {
		return bad("peak is required")
	}
	if f.Peak.StartHour < 0 || f.Peak.EndHour > 24 || f.Peak.StartHour >= f.Peak.EndHour {
		return bad("bad peak hours %d-%d", f.Peak.StartHour, f.Peak.EndHour)
	}
	inc, err := ParseIncrement(f.Increment)
	if err != nil {
		return bad("%v", err)
	}
	p := &TieredPlan{Code: f.Code, Location: loc, PeakStartHour: f.Peak.StartHour,
		PeakEndHour: f.Peak.EndHour, Holidays: map[string]bool{}, Increment: inc}
	for _, h := range f.Holidays {
		if _, err := time.Parse("2006-01-02", h); err != nil {
			return bad("bad holiday %q", h)
		}
		p.Holidays[h] = true
	}
	if f.SetupFee != "" {
		fee, err := money.Parse(f.SetupFee)
		if err != nil || fee < 0 {
			return bad("bad setup_fee %q", f.SetupFee)
		}
		p.SetupFee = fee
	}
	if len(f.Tiers) == 0 {
		return bad("at least one tier is required")
	}
	var prev int64
	for i, t := range f.Tiers {
		last := i == len(f.Tiers)-1
		if last && t.UpToMinutes != 0 {
			return bad("last tier must be unlimited (up_to_minutes 0)")
		}
		if !last && (t.UpToMinutes <= prev) {
			return bad("tier %d: up_to_minutes must be positive and increasing", i)
		}
		peak, err1 := money.Parse(t.Peak)
		off, err2 := money.Parse(t.OffPeak)
		if err1 != nil || err2 != nil || peak < 0 || off < 0 {
			return bad("tier %d: bad rate", i)
		}
		p.Tiers = append(p.Tiers, Tier{UpToSeconds: t.UpToMinutes * 60, Peak: peak, OffPeak: off})
		if !last {
			prev = t.UpToMinutes
		}
	}
	return p, nil
}
