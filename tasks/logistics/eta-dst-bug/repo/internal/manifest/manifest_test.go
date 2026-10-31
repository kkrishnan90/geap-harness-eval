package manifest

import "testing"

func TestChargeableKg(t *testing.T) {
	items := []Item{{SKU: "PAL-EUR", Qty: 10, WeightKg: 120, LengthM: 1.2, WidthM: 0.8, HeightM: 1.5}}
	// volumetric 10*1.44 m3*333 = 4795.2 > 1200
	if got := ChargeableKg(items); got != 4796 {
		t.Fatalf("chargeable = %v", got)
	}
}

func TestLoadingMetresStackable(t *testing.T) {
	items := []Item{
		{SKU: "PAL-EUR", Qty: 33, LengthM: 1.2, WidthM: 0.8},
		{SKU: "PAL-EUR-S", Qty: 4, LengthM: 1.2, WidthM: 0.8, Stackable: true},
	}
	ldm, err := LoadingMetres(items)
	if err != nil {
		t.Fatal(err)
	}
	if ldm != 14.0 {
		t.Fatalf("ldm = %v", ldm)
	}
	u, _ := Utilisation(items)
	if u != 102.9 {
		t.Fatalf("utilisation = %v", u)
	}
	if _, err := LoadingMetres([]Item{{Qty: -1}}); err == nil {
		t.Fatal("expected error")
	}
}
