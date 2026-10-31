package geo

import (
	"math"
	"testing"
	"time"
)

func TestDistanceKm(t *testing.T) {
	ham := Point{53.5511, 9.9937}
	ber := Point{52.5200, 13.4050}
	d := DistanceKm(ham, ber)
	if math.Abs(d-255.3) > 1.0 {
		t.Fatalf("HAM-BER = %.1f km", d)
	}
	if DistanceKm(ham, ham) != 0 {
		t.Fatal("zero distance expected")
	}
}

func TestPlannedDriveRoundsUpToFiveMinutes(t *testing.T) {
	d := PlannedDrive(Point{53.5511, 9.9937}, Point{52.5200, 13.4050}, 70)
	if d%(5*time.Minute) != 0 || d < 4*time.Hour || d > 5*time.Hour {
		t.Fatalf("planned drive = %s", d)
	}
	if PlannedDrive(Point{}, Point{1, 1}, 0) != 0 {
		t.Fatal("zero speed must yield 0")
	}
}
