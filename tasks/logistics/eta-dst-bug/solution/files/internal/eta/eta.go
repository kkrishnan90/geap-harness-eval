// Package eta computes line-haul ETAs: drive time with statutory breaks, hub dwell and
// receiving windows.
package eta

import (
	"errors"
	"fmt"
	"time"

	"github.com/northline/fleetroute/internal/hubs"
)

// Statutory driving rule (EU 561/2006 style, applied network-wide): after MaxContinuousDrive
// of cumulative driving a Break must be taken before driving on.
const (
	MaxContinuousDrive = 4*time.Hour + 30*time.Minute
	Break              = 45 * time.Minute
)

// Leg is one drive between two hubs.
type Leg struct {
	To    string
	Drive time.Duration
}

// Stop is the computed timeline at one hub.
type Stop struct {
	Hub      string
	Arrival  time.Time // truck arrives at the gate (hub local time)
	Accepted time.Time // dock accepts the trailer (receiving window), hub local time
	Depart   time.Time // after dwell, hub local time
}

// Result is the full plan for a route.
type Result struct {
	Stops []Stop
	// ETA is when the final hub accepts the trailer, in that hub's local time.
	ETA time.Time
	// Transit is the elapsed time from departure to ETA.
	Transit time.Duration
}

// Planner computes ETAs against a hub registry.
type Planner struct {
	Hubs *hubs.Registry
}

// ErrUnknownHub is returned for a hub code that is not in the registry.
var ErrUnknownHub = errors.New("unknown hub")

// driving tracks cumulative driving since the last break across legs.
type driving struct {
	sinceBreak time.Duration
}

// addDrive advances t by d of driving, inserting statutory breaks.
func (dr *driving) addDrive(t time.Time, d time.Duration) time.Time {
	for d > 0 {
		chunk := MaxContinuousDrive - dr.sinceBreak
		if chunk > d {
			chunk = d
		}
		t = t.Add(chunk)
		d -= chunk
		dr.sinceBreak += chunk
		if dr.sinceBreak >= MaxContinuousDrive && d > 0 {
			t = t.Add(Break)
			dr.sinceBreak = 0
		}
	}
	return t
}

// acceptAt returns the earliest instant >= t at which hub h receives goods.
func acceptAt(h hubs.Hub, t time.Time) time.Time {
	local := t.In(h.Location)
	if h.AlwaysOpen() {
		return local
	}
	// Window boundaries are local wall-clock times; build them with time.Date so a DST
	// change on that day (or night) is respected.
	y, m, d := local.Date()
	open := time.Date(y, m, d, h.OpenHour, 0, 0, 0, h.Location)
	closeT := time.Date(y, m, d, h.CloseHour, 0, 0, 0, h.Location)
	switch {
	case local.Before(open):
		return open
	case local.Before(closeT):
		return local
	default:
		return time.Date(y, m, d+1, h.OpenHour, 0, 0, 0, h.Location)
	}
}

// Estimate plans a route departing origin at depart (any location) over legs.
// The origin's dwell is not applied (the trailer is already loaded).
func (p *Planner) Estimate(origin string, depart time.Time, legs []Leg) (Result, error) {
	if len(legs) == 0 {
		return Result{}, errors.New("route has no legs")
	}
	o, ok := p.Hubs.Get(origin)
	if !ok {
		return Result{}, fmt.Errorf("%w: %s", ErrUnknownHub, origin)
	}
	t := depart.In(o.Location)
	var dr driving
	res := Result{}
	for i, leg := range legs {
		h, ok := p.Hubs.Get(leg.To)
		if !ok {
			return Result{}, fmt.Errorf("%w: %s", ErrUnknownHub, leg.To)
		}
		if leg.Drive <= 0 {
			return Result{}, fmt.Errorf("leg %d: drive time must be positive", i)
		}
		arrival := dr.addDrive(t, leg.Drive).In(h.Location)
		accepted := acceptAt(h, arrival)
		if accepted.Sub(arrival) >= Break {
			// Waiting at the gate counts as a break.
			dr.sinceBreak = 0
		}
		dep := accepted.Add(h.Dwell)
		res.Stops = append(res.Stops, Stop{Hub: h.Code, Arrival: arrival, Accepted: accepted, Depart: dep})
		t = dep
		if h.Dwell >= Break {
			dr.sinceBreak = 0
		}
	}
	last := res.Stops[len(res.Stops)-1]
	res.ETA = last.Accepted
	res.Transit = res.ETA.Sub(depart)
	return res, nil
}
