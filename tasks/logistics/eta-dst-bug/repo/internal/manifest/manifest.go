// Package manifest computes trailer utilisation for a load.
package manifest

import (
	"errors"
	"math"
)

// Volumetric divisor (kg per m3) used for chargeable weight on line-haul.
const VolumetricKgPerM3 = 333.0

// StandardTrailerLdm is the loading length of a 13.6 m curtain-sider.
const StandardTrailerLdm = 13.6

// Item is one handling unit.
type Item struct {
	SKU       string
	Qty       int
	WeightKg  float64
	LengthM   float64
	WidthM    float64
	HeightM   float64
	Stackable bool
}

// ChargeableKg is max(actual, volumetric) over all items, rounded up to whole kg.
func ChargeableKg(items []Item) float64 {
	var actual, vol float64
	for _, it := range items {
		actual += float64(it.Qty) * it.WeightKg
		vol += float64(it.Qty) * it.LengthM * it.WidthM * it.HeightM
	}
	return math.Ceil(math.Max(actual, vol*VolumetricKgPerM3))
}

// LoadingMetres: floor area / trailer width (2.4 m); stackable units count once per 2 high.
func LoadingMetres(items []Item) (float64, error) {
	var area float64
	for _, it := range items {
		if it.Qty < 0 {
			return 0, errors.New("negative quantity")
		}
		positions := float64(it.Qty)
		if it.Stackable {
			positions = math.Ceil(positions / 2)
		}
		area += positions * it.LengthM * it.WidthM
	}
	return math.Round(area/2.4*100) / 100, nil
}

// Utilisation of a standard trailer in percent (may exceed 100 for overloads).
func Utilisation(items []Item) (float64, error) {
	ldm, err := LoadingMetres(items)
	if err != nil {
		return 0, err
	}
	return math.Round(ldm/StandardTrailerLdm*1000) / 10, nil
}
