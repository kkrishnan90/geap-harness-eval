// Package quota enforces per network-slice admission quotas.
//
// Every slice has an aggregate token bucket shared by all of its subscribers
// and a per-subscriber bucket template. One token is one byte of admitted
// traffic (or one request, depending on how the caller uses it).
package quota

import (
	"errors"
	"fmt"

	"telco.example/pcf-quota/internal/snssai"
)

// BucketSpec configures one token bucket.
type BucketSpec struct {
	RatePerSec int64 `json:"rate_per_sec"` // tokens added per second
	Burst      int64 `json:"burst"`        // capacity; buckets start full
}

// SliceSpec configures the quota of one slice.
type SliceSpec struct {
	Slice         snssai.SNSSAI
	Aggregate     BucketSpec
	PerSubscriber BucketSpec
}

// ErrInvalidSpec wraps every configuration error.
var ErrInvalidSpec = errors.New("quota: invalid spec")

// Validate checks one bucket spec.
func (b BucketSpec) Validate() error {
	if b.RatePerSec <= 0 || b.RatePerSec > 1_000_000_000_000 {
		return fmt.Errorf("%w: rate_per_sec %d out of range (1..1e12)", ErrInvalidSpec, b.RatePerSec)
	}
	if b.Burst <= 0 {
		return fmt.Errorf("%w: burst %d must be positive", ErrInvalidSpec, b.Burst)
	}
	return nil
}

// Validate checks a slice spec.
func (s SliceSpec) Validate() error {
	if err := s.Aggregate.Validate(); err != nil {
		return fmt.Errorf("slice %s aggregate: %w", s.Slice, err)
	}
	if err := s.PerSubscriber.Validate(); err != nil {
		return fmt.Errorf("slice %s per-subscriber: %w", s.Slice, err)
	}
	return nil
}

// ValidateAll checks every spec and rejects duplicate slices.
func ValidateAll(specs []SliceSpec) error {
	seen := make(map[snssai.SNSSAI]bool, len(specs))
	for _, s := range specs {
		if err := s.Validate(); err != nil {
			return err
		}
		if seen[s.Slice] {
			return fmt.Errorf("%w: duplicate slice %s", ErrInvalidSpec, s.Slice)
		}
		seen[s.Slice] = true
	}
	return nil
}
