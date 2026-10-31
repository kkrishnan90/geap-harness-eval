package rating

import (
	"sort"
	"strings"
)

// Zone is a destination zone selected by longest matching E.164 prefix.
type Zone struct {
	Name   string
	Prefix string // digits after '+', e.g. "3491"
}

// ZoneTable resolves destinations to zones.
type ZoneTable struct {
	zones []Zone // sorted by prefix length, longest first
}

// NewZoneTable builds a table; later duplicates of a prefix replace earlier ones.
func NewZoneTable(zones []Zone) *ZoneTable {
	byPrefix := map[string]Zone{}
	for _, z := range zones {
		byPrefix[z.Prefix] = z
	}
	t := &ZoneTable{}
	for _, z := range byPrefix {
		t.zones = append(t.zones, z)
	}
	sort.Slice(t.zones, func(i, j int) bool {
		if len(t.zones[i].Prefix) != len(t.zones[j].Prefix) {
			return len(t.zones[i].Prefix) > len(t.zones[j].Prefix)
		}
		return t.zones[i].Prefix < t.zones[j].Prefix
	})
	return t
}

// Lookup returns the zone for an E.164 number ("+34911234567").
func (t *ZoneTable) Lookup(e164 string) (Zone, bool) {
	digits := strings.TrimPrefix(e164, "+")
	for _, z := range t.zones {
		if strings.HasPrefix(digits, z.Prefix) {
			return z, true
		}
	}
	return Zone{}, false
}
