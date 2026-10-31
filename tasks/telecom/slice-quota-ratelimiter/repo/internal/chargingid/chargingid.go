// Package chargingid allocates 32-bit charging identifiers that are unique per
// PCF instance: the top 6 bits carry the instance number, the rest a counter.
package chargingid

import (
	"errors"
	"sync/atomic"
)

const instanceBits = 6
const counterBits = 32 - instanceBits
const counterMask = 1<<counterBits - 1

// Allocator is safe for concurrent use.
type Allocator struct {
	instance uint32
	next     atomic.Uint32
}

// New returns an allocator for instance 0..63.
func New(instance uint32) (*Allocator, error) {
	if instance >= 1<<instanceBits {
		return nil, errors.New("chargingid: instance out of range")
	}
	return &Allocator{instance: instance}, nil
}

// Next returns the next charging ID. The counter wraps and skips 0.
func (a *Allocator) Next() uint32 {
	for {
		c := a.next.Add(1) & counterMask
		if c != 0 {
			return a.instance<<counterBits | c
		}
	}
}

// Instance extracts the instance number from an ID.
func Instance(id uint32) uint32 { return id >> counterBits }
