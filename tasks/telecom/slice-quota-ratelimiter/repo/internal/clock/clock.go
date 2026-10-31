// Package clock abstracts time for code on the admission path.
package clock

import (
	"sync"
	"time"
)

// Clock returns the current time.
type Clock interface {
	Now() time.Time
}

// System is the production clock.
type System struct{}

// Now implements Clock.
func (System) Now() time.Time { return time.Now() }

// Fake is a manually advanced clock, safe for concurrent use.
type Fake struct {
	mu  sync.Mutex
	now time.Time
}

// NewFake returns a Fake clock set to t.
func NewFake(t time.Time) *Fake { return &Fake{now: t} }

// Now implements Clock.
func (f *Fake) Now() time.Time {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.now
}

// Advance moves the clock forward by d (d must be >= 0).
func (f *Fake) Advance(d time.Duration) {
	if d < 0 {
		panic("clock: negative advance")
	}
	f.mu.Lock()
	f.now = f.now.Add(d)
	f.mu.Unlock()
}

// Set jumps to t (used to simulate NTP steps in tests; may go backwards).
func (f *Fake) Set(t time.Time) {
	f.mu.Lock()
	f.now = t
	f.mu.Unlock()
}
