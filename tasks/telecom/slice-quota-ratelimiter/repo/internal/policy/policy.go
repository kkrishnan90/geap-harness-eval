// Package policy loads slice quota policies distributed by the OAM system.
package policy

import (
	"encoding/json"
	"fmt"
	"io"
	"os"

	"telco.example/pcf-quota/internal/quota"
	"telco.example/pcf-quota/internal/snssai"
)

type fileSlice struct {
	SNSSAI        string           `json:"snssai"`
	Aggregate     quota.BucketSpec `json:"aggregate"`
	PerSubscriber quota.BucketSpec `json:"per_subscriber"`
}

type file struct {
	Version int         `json:"version"`
	Slices  []fileSlice `json:"slices"`
}

// Decode parses and validates a policy document.
func Decode(r io.Reader) ([]quota.SliceSpec, error) {
	dec := json.NewDecoder(r)
	dec.DisallowUnknownFields()
	var f file
	if err := dec.Decode(&f); err != nil {
		return nil, fmt.Errorf("policy: %w", err)
	}
	if f.Version != 1 {
		return nil, fmt.Errorf("policy: unsupported version %d", f.Version)
	}
	specs := make([]quota.SliceSpec, 0, len(f.Slices))
	for _, s := range f.Slices {
		id, err := snssai.Parse(s.SNSSAI)
		if err != nil {
			return nil, fmt.Errorf("policy: %w", err)
		}
		specs = append(specs, quota.SliceSpec{Slice: id, Aggregate: s.Aggregate, PerSubscriber: s.PerSubscriber})
	}
	if err := quota.ValidateAll(specs); err != nil {
		return nil, fmt.Errorf("policy: %w", err)
	}
	return specs, nil
}

// LoadFile reads a policy JSON file.
func LoadFile(path string) ([]quota.SliceSpec, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	return Decode(f)
}
