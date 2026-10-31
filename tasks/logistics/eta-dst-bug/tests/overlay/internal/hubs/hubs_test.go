package hubs

import (
	"strings"
	"testing"
	"time"
)

func TestDefaultRegistryParses(t *testing.T) {
	r, err := Parse(Default)
	if err != nil {
		t.Fatal(err)
	}
	if len(r.Codes()) != 9 {
		t.Fatalf("codes = %v", r.Codes())
	}
	h, ok := r.Get("nyc")
	if !ok || h.OpenHour != 6 || h.CloseHour != 22 || h.Dwell != 30*time.Minute {
		t.Fatalf("NYC = %+v", h)
	}
	if h.Location.String() != "America/New_York" {
		t.Fatalf("zone = %s", h.Location)
	}
	if b, _ := r.Get("BER"); !b.AlwaysOpen() {
		t.Fatal("BER should be 24/7")
	}
}

func TestParseErrors(t *testing.T) {
	cases := map[string]string{
		"fields": "A|B|UTC|0-24",
		"zone":   "A|B|Mars/Olympus|0-24|10",
		"window": "A|B|UTC|22-6|10",
		"dwell":  "A|B|UTC|0-24|-5",
		"dup":    "A|B|UTC|0-24|1\nA|C|UTC|0-24|1",
	}
	for name, src := range cases {
		if _, err := Parse(src); err == nil {
			t.Errorf("%s: expected error", name)
		} else if !strings.Contains(err.Error(), "line") {
			t.Errorf("%s: error should carry line number: %v", name, err)
		}
	}
}
