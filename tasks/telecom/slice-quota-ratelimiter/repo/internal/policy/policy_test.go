package policy

import (
	"strings"
	"testing"
)

const doc = `{"version":1,"slices":[
 {"snssai":"1-000001","aggregate":{"rate_per_sec":125000000,"burst":250000000},"per_subscriber":{"rate_per_sec":12500000,"burst":25000000}},
 {"snssai":"2","aggregate":{"rate_per_sec":1000,"burst":1000},"per_subscriber":{"rate_per_sec":10,"burst":20}}]}`

func TestPolicyDecode(t *testing.T) {
	specs, err := Decode(strings.NewReader(doc))
	if err != nil {
		t.Fatal(err)
	}
	if len(specs) != 2 || specs[1].PerSubscriber.Burst != 20 || specs[0].Slice.String() != "1-000001" {
		t.Fatalf("got %+v", specs)
	}
}

func TestPolicyRejectsUnknownField(t *testing.T) {
	if _, err := Decode(strings.NewReader(`{"version":1,"slices":[],"extra":1}`)); err == nil {
		t.Fatal("expected error")
	}
}

func TestPolicyRejectsVersion(t *testing.T) {
	if _, err := Decode(strings.NewReader(`{"version":2,"slices":[]}`)); err == nil {
		t.Fatal("expected error")
	}
}
