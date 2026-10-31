// Package rating prices CDRs against tariff plans.
package rating

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"

	"github.com/telcoridge/mediation/internal/cdr"
	"github.com/telcoridge/mediation/internal/money"
)

// ErrNoZone is returned when a destination matches no zone of the plan.
var ErrNoZone = errors.New("rating: destination not in any zone")

// FlatPlan is the legacy per-second plan: one per-minute rate per destination zone,
// billed per second, rounded half-up per call.
type FlatPlan struct {
	Code  string
	Zones *ZoneTable
	Rates map[string]money.Money // zone name -> per-minute rate
}

// RateFlat prices one record. Unanswered calls cost nothing.
func RateFlat(rec cdr.Record, p *FlatPlan) (money.Money, error) {
	if !rec.Answered || rec.DurationSec == 0 {
		return 0, nil
	}
	if rec.DurationSec < 0 {
		return 0, fmt.Errorf("rating: %s: negative duration", rec.ID)
	}
	z, ok := p.Zones.Lookup(rec.Called)
	if !ok {
		return 0, fmt.Errorf("%w: %s", ErrNoZone, rec.Called)
	}
	rate, ok := p.Rates[z.Name]
	if !ok {
		return 0, fmt.Errorf("rating: plan %s has no rate for zone %s", p.Code, z.Name)
	}
	return money.PerMinute(rate, rec.DurationSec), nil
}

type flatFile struct {
	Code  string `json:"code"`
	Zones []struct {
		Name   string `json:"name"`
		Prefix string `json:"prefix"`
		Rate   string `json:"rate_per_minute"`
	} `json:"zones"`
}

// LoadFlatPlan reads a flat tariff file (see testdata/flat.json).
func LoadFlatPlan(r io.Reader) (*FlatPlan, error) {
	var f flatFile
	dec := json.NewDecoder(r)
	dec.DisallowUnknownFields()
	if err := dec.Decode(&f); err != nil {
		return nil, fmt.Errorf("rating: flat plan: %w", err)
	}
	if f.Code == "" || len(f.Zones) == 0 {
		return nil, errors.New("rating: flat plan: code and zones are required")
	}
	p := &FlatPlan{Code: f.Code, Rates: map[string]money.Money{}}
	var zones []Zone
	for _, z := range f.Zones {
		rate, err := money.Parse(z.Rate)
		if err != nil || rate < 0 {
			return nil, fmt.Errorf("rating: flat plan: zone %s: bad rate %q", z.Name, z.Rate)
		}
		zones = append(zones, Zone{Name: z.Name, Prefix: z.Prefix})
		p.Rates[z.Name] = rate
	}
	p.Zones = NewZoneTable(zones)
	return p, nil
}
