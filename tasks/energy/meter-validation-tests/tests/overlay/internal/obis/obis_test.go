package obis

import "testing"

func TestObisParseFull(t *testing.T) {
	c, err := Parse("1-0:2.8.1*255")
	if err != nil || c.String() != "1-0:2.8.1*255" || c.IsActiveImport() {
		t.Fatalf("got %v %v", c, err)
	}
}

func TestObisParseShort(t *testing.T) {
	c, err := Parse("1.8.0")
	if err != nil || c.String() != "1-0:1.8.0*255" || !c.IsActiveImport() {
		t.Fatalf("got %v %v", c, err)
	}
}

func TestObisParseErrors(t *testing.T) {
	for _, s := range []string{"1-0", "1.8", "x.8.0", "1-0:1.8.0*999"} {
		if _, err := Parse(s); err == nil {
			t.Errorf("%q: expected error", s)
		}
	}
}
