// Package geo has distance and drive-time heuristics used when no routed time is available.
package geo

import (
	"math"
	"time"
)

const earthRadiusKm = 6371.0088

// Point is a WGS84 coordinate.
type Point struct{ Lat, Lon float64 }

// DistanceKm is the great-circle (haversine) distance.
func DistanceKm(a, b Point) float64 {
	rad := math.Pi / 180
	dLat := (b.Lat - a.Lat) * rad
	dLon := (b.Lon - a.Lon) * rad
	h := math.Sin(dLat/2)*math.Sin(dLat/2) +
		math.Cos(a.Lat*rad)*math.Cos(b.Lat*rad)*math.Sin(dLon/2)*math.Sin(dLon/2)
	return 2 * earthRadiusKm * math.Asin(math.Sqrt(h))
}

// RoadFactor converts great-circle distance into expected road distance.
const RoadFactor = 1.22

// PlannedDrive estimates drive time at an average line-haul speed (km/h), rounded up to
// the next 5 minutes as the planners do.
func PlannedDrive(a, b Point, avgKmh float64) time.Duration {
	if avgKmh <= 0 {
		return 0
	}
	hours := DistanceKm(a, b) * RoadFactor / avgKmh
	minutes := math.Ceil(hours*60/5) * 5
	return time.Duration(minutes) * time.Minute
}
