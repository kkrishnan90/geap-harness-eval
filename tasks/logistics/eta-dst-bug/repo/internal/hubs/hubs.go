// Package hubs holds the hub (cross-dock / distribution centre) registry.
package hubs

import (
	"bufio"
	"fmt"
	"strconv"
	"strings"
	"time"
	_ "time/tzdata" // deterministic zone data regardless of host
)

// Hub is a site trucks can arrive at.
type Hub struct {
	Code     string
	Name     string
	Location *time.Location
	// Receiving window in local wall-clock hours: goods are accepted from OpenHour:00
	// (inclusive) to CloseHour:00 (exclusive). 0/24 means the dock is open around the clock.
	OpenHour  int
	CloseHour int
	// Handling time once a trailer is accepted at the dock.
	Dwell time.Duration
}

// AlwaysOpen reports whether the hub receives 24/7.
func (h Hub) AlwaysOpen() bool { return h.OpenHour == 0 && h.CloseHour == 24 }

// Registry indexes hubs by code.
type Registry struct {
	byCode map[string]Hub
}

// Get returns the hub with the given code.
func (r *Registry) Get(code string) (Hub, bool) {
	h, ok := r.byCode[strings.ToUpper(code)]
	return h, ok
}

// Codes returns all hub codes (unordered).
func (r *Registry) Codes() []string {
	out := make([]string, 0, len(r.byCode))
	for c := range r.byCode {
		out = append(out, c)
	}
	return out
}

// Parse reads the registry format exported by the master-data service:
//
//	CODE|Name|IANA zone|open-close|dwell minutes
//
// Blank lines and lines starting with '#' are ignored.
func Parse(src string) (*Registry, error) {
	r := &Registry{byCode: map[string]Hub{}}
	sc := bufio.NewScanner(strings.NewReader(src))
	line := 0
	for sc.Scan() {
		line++
		text := strings.TrimSpace(sc.Text())
		if text == "" || strings.HasPrefix(text, "#") {
			continue
		}
		f := strings.Split(text, "|")
		if len(f) != 5 {
			return nil, fmt.Errorf("line %d: want 5 fields, got %d", line, len(f))
		}
		loc, err := time.LoadLocation(strings.TrimSpace(f[2]))
		if err != nil {
			return nil, fmt.Errorf("line %d: %w", line, err)
		}
		window := strings.SplitN(strings.TrimSpace(f[3]), "-", 2)
		if len(window) != 2 {
			return nil, fmt.Errorf("line %d: bad window %q", line, f[3])
		}
		open, err1 := strconv.Atoi(window[0])
		closeH, err2 := strconv.Atoi(window[1])
		if err1 != nil || err2 != nil || open < 0 || closeH > 24 || open >= closeH {
			return nil, fmt.Errorf("line %d: bad window %q", line, f[3])
		}
		dwell, err := strconv.Atoi(strings.TrimSpace(f[4]))
		if err != nil || dwell < 0 {
			return nil, fmt.Errorf("line %d: bad dwell %q", line, f[4])
		}
		code := strings.ToUpper(strings.TrimSpace(f[0]))
		if _, dup := r.byCode[code]; dup {
			return nil, fmt.Errorf("line %d: duplicate hub %s", line, code)
		}
		r.byCode[code] = Hub{
			Code: code, Name: strings.TrimSpace(f[1]), Location: loc,
			OpenHour: open, CloseHour: closeH, Dwell: time.Duration(dwell) * time.Minute,
		}
	}
	return r, sc.Err()
}

// Default is the production network snapshot (master data export 2026-09).
const Default = `
# code|name|zone|window|dwell
CHI|Chicago Joliet XD|America/Chicago|0-24|45
NYC|Newark Port DC|America/New_York|6-22|30
ATL|Atlanta South XD|America/New_York|0-24|40
DEN|Denver Commerce City|America/Denver|5-21|30
LAX|Ontario CA DC|America/Los_Angeles|6-22|35
BER|Berlin Schoenefeld XD|Europe/Berlin|0-24|30
HAM|Hamburg Billbrook DC|Europe/Berlin|6-22|30
LON|London Dagenham DC|Europe/London|6-22|30
MAD|Madrid Coslada XD|Europe/Madrid|0-24|40
`
