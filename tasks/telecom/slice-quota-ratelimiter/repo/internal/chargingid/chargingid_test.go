package chargingid

import "testing"

func TestChargingIDInstanceBits(t *testing.T) {
	a, _ := New(42)
	id := a.Next()
	if Instance(id) != 42 || id&counterMask != 1 {
		t.Fatalf("id %#x", id)
	}
}

func TestChargingIDRejectsInstance(t *testing.T) {
	if _, err := New(64); err == nil {
		t.Fatal("expected error")
	}
}
