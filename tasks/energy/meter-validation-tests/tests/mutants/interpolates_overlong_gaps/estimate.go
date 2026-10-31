package vee

import (
	"time"

	"grid.example/mdm/internal/interval"
)

// interpolate returns round-half-up(prev + (next-prev)*i/(k+1)) for
// non-negative prev/next.
func interpolate(prev, next int64, i, k int) int64 {
	den := int64(k + 1)
	num := prev*den + (next-prev)*int64(i)
	return (2*num + den) / (2 * den)
}

func usable(r interval.Reading, cfg Config) bool {
	return r.Wh >= 0 && r.Wh <= cfg.MaxWh
}

// Estimate fills short gaps inside [from, to) by linear interpolation.
// It returns only the estimated readings, sorted by Start.
func Estimate(readings []interval.Reading, from, to time.Time, cfg Config) []interval.Reading {
	kept, _ := accepted(readings, from, to, cfg)
	var out []interval.Reading
	var slots []time.Time
	for t := from; t.Before(to); t = t.Add(cfg.Interval) {
		slots = append(slots, t)
	}
	for i := 0; i < len(slots); {
		if _, ok := kept[slots[i].UnixNano()]; ok {
			i++
			continue
		}
		j := i
		for j < len(slots) {
			if _, ok := kept[slots[j].UnixNano()]; ok {
				break
			}
			j++
		}
		k := j - i
		if i > 0 && j < len(slots) && k <= cfg.MaxInterpolate+1 {
			prev, next := kept[slots[i-1].UnixNano()], kept[slots[j].UnixNano()]
			if usable(prev, cfg) && usable(next, cfg) {
				for n := 1; n <= k; n++ {
					out = append(out, interval.Reading{
						MeterID: prev.MeterID,
						Start:   slots[i+n-1],
						Wh:      interpolate(prev.Wh, next.Wh, n, k),
						Flags:   interval.FlagEstimated,
					})
				}
			}
		}
		i = j
	}
	return out
}
