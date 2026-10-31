package snssai

import "testing"

func TestSnssaiParseRoundTrip(t *testing.T) {
	for _, s := range []string{"1", "1-000001", "2-abcdef", "255-ffff00"} {
		v, err := Parse(s)
		if err != nil {
			t.Fatalf("%s: %v", s, err)
		}
		if v.String() != s {
			t.Errorf("round trip %q -> %q", s, v.String())
		}
	}
}

func TestSnssaiParseNoSD(t *testing.T) {
	v := MustParse("3")
	if v.SD != NoSD || v.SST != SSTMIoT {
		t.Fatalf("got %+v", v)
	}
}

func TestSnssaiParseErrors(t *testing.T) {
	for _, s := range []string{"", "256", "1-12345", "1-zzzzzz", "x-000001"} {
		if _, err := Parse(s); err == nil {
			t.Errorf("%q: expected error", s)
		}
	}
}

func TestSnssaiNewRejectsWideSD(t *testing.T) {
	if _, err := New(1, 0x1000000); err == nil {
		t.Fatal("expected error")
	}
}
