// Package audit records statement downloads for the compliance trail.
package audit

import (
	"sync"
	"time"
)

// Entry is one download attempt.
type Entry struct {
	At       time.Time
	Customer string
	Name     string
	Status   int
}

// Log is an in-memory, append-only audit log (shipped to the SIEM by a sidecar).
type Log struct {
	mu      sync.Mutex
	entries []Entry
	now     func() time.Time
}

// NewLog returns an empty log using clock now (nil = time.Now).
func NewLog(now func() time.Time) *Log {
	if now == nil {
		now = time.Now
	}
	return &Log{now: now}
}

// Record appends an entry.
func (l *Log) Record(customer, name string, status int) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.entries = append(l.entries, Entry{At: l.now().UTC(), Customer: customer, Name: name, Status: status})
}

// Entries returns a copy of all entries.
func (l *Log) Entries() []Entry {
	l.mu.Lock()
	defer l.mu.Unlock()
	return append([]Entry(nil), l.entries...)
}
