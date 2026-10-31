// Package vee implements the MDM validation, estimation and editing rules
// described in docs/vee-rules.md.
package vee

import "time"

// Config parameterises the rules.
type Config struct {
	Interval       time.Duration // slot length, 15 minutes in production
	MaxWh          int64         // HIGH above this value
	FlatlineCount  int           // FLATLINE at this many identical non-zero slots
	MaxInterpolate int           // longest gap (in slots) that Estimate fills
}

// DefaultConfig is the production configuration for residential meters.
func DefaultConfig() Config {
	return Config{Interval: 15 * time.Minute, MaxWh: 25_000, FlatlineCount: 8, MaxInterpolate: 4}
}

// Code identifies a validation rule.
type Code string

// Validation codes.
const (
	CodeDuplicate  Code = "DUPLICATE"
	CodeFlatline   Code = "FLATLINE"
	CodeGap        Code = "GAP"
	CodeHigh       Code = "HIGH"
	CodeMisaligned Code = "MISALIGNED"
	CodeNegative   Code = "NEGATIVE"
)

// Issue is one validation finding.
type Issue struct {
	Code  Code
	Start time.Time
}
