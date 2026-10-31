package vee

import (
	"sort"
	"time"

	"grid.example/mdm/internal/interval"
)

func aligned(t time.Time, step time.Duration) bool {
	return t.UnixNano()%int64(step) == 0
}

// accepted returns the readings that the other rules look at (aligned,
// inside the window, first per slot) keyed by slot start, plus the issues
// found while filtering.
func accepted(readings []interval.Reading, from, to time.Time, cfg Config) (map[int64]interval.Reading, []Issue) {
	kept := make(map[int64]interval.Reading)
	var issues []Issue
	for _, r := range readings {
		if r.Start.Before(from) || !r.Start.Before(to) {
			continue
		}
		if !aligned(r.Start, cfg.Interval) {
			issues = append(issues, Issue{CodeMisaligned, r.Start})
			continue
		}
		key := r.Start.UnixNano()
		if _, dup := kept[key]; dup {
			issues = append(issues, Issue{CodeDuplicate, r.Start})
			continue
		}
		kept[key] = r
	}
	return kept, issues
}

// Validate applies the validation rules to readings inside [from, to).
func Validate(readings []interval.Reading, from, to time.Time, cfg Config) []Issue {
	kept, issues := accepted(readings, from, to, cfg)
	var last time.Time
	for _, r := range kept {
		if r.Start.After(last) {
			last = r.Start
		}
	}

	runStart := time.Time{}
	runLen := 0
	var runWh int64
	reported := false
	for t := from; t.Before(to); t = t.Add(cfg.Interval) {
		r, ok := kept[t.UnixNano()]
		if !ok {
			if !t.After(last) {
				issues = append(issues, Issue{CodeGap, t})
			}
			runLen = 0
			continue
		}
		if r.Wh < 0 {
			issues = append(issues, Issue{CodeNegative, t})
		}
		if r.Wh > cfg.MaxWh {
			issues = append(issues, Issue{CodeHigh, t})
		}
		if r.Wh != 0 && runLen > 0 && r.Wh == runWh {
			runLen++
		} else if r.Wh != 0 {
			runStart, runLen, runWh, reported = t, 1, r.Wh, false
		} else {
			runLen = 0
		}
		if runLen >= cfg.FlatlineCount && !reported {
			issues = append(issues, Issue{CodeFlatline, runStart})
			reported = true
		}
	}

	sort.SliceStable(issues, func(i, j int) bool {
		if !issues[i].Start.Equal(issues[j].Start) {
			return issues[i].Start.Before(issues[j].Start)
		}
		return issues[i].Code < issues[j].Code
	})
	return issues
}
