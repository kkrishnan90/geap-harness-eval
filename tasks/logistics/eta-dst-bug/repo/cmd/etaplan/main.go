// Command etaplan prints a route timeline: etaplan ORIGIN 2026-03-28T22:00 DEST:DRIVE [DEST:DRIVE...]
package main

import (
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/northline/fleetroute/internal/eta"
	"github.com/northline/fleetroute/internal/hubs"
)

func main() {
	if len(os.Args) < 4 {
		fmt.Fprintln(os.Stderr, "usage: etaplan ORIGIN YYYY-MM-DDTHH:MM DEST:DRIVE...")
		os.Exit(2)
	}
	reg, err := hubs.Parse(hubs.Default)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	origin, ok := reg.Get(os.Args[1])
	if !ok {
		fmt.Fprintln(os.Stderr, "unknown origin")
		os.Exit(1)
	}
	depart, err := time.ParseInLocation("2006-01-02T15:04", os.Args[2], origin.Location)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	var legs []eta.Leg
	for _, a := range os.Args[3:] {
		to, d, _ := strings.Cut(a, ":")
		dur, err := time.ParseDuration(d)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		legs = append(legs, eta.Leg{To: to, Drive: dur})
	}
	p := eta.Planner{Hubs: reg}
	res, err := p.Estimate(origin.Code, depart, legs)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	for _, s := range res.Stops {
		fmt.Printf("%-4s arrive %s  accepted %s  depart %s\n", s.Hub,
			s.Arrival.Format(time.RFC3339), s.Accepted.Format(time.RFC3339), s.Depart.Format(time.RFC3339))
	}
	fmt.Printf("ETA %s (transit %s)\n", res.ETA.Format(time.RFC3339), res.Transit)
}
