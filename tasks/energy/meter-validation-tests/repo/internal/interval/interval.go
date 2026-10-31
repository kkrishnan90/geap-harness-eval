// Package interval holds interval meter readings.
package interval

import (
	"encoding/csv"
	"fmt"
	"io"
	"strconv"
	"strings"
	"time"
)

// Flags on a reading.
type Flags uint8

// Reading flags.
const (
	FlagEstimated Flags = 1 << iota
	FlagEdited
	FlagPowerOutage
)

// Reading is the energy measured in one interval starting at Start.
type Reading struct {
	MeterID string
	Start   time.Time
	Wh      int64
	Flags   Flags
}

// DecodeCSV reads "meter_id,start_rfc3339,wh[,flags]" lines (header optional).
func DecodeCSV(r io.Reader) ([]Reading, error) {
	cr := csv.NewReader(r)
	cr.FieldsPerRecord = -1
	var out []Reading
	for line := 1; ; line++ {
		rec, err := cr.Read()
		if err == io.EOF {
			return out, nil
		}
		if err != nil {
			return nil, err
		}
		if line == 1 && strings.EqualFold(rec[0], "meter_id") {
			continue
		}
		if len(rec) < 3 {
			return nil, fmt.Errorf("line %d: want at least 3 fields", line)
		}
		t, err := time.Parse(time.RFC3339, rec[1])
		if err != nil {
			return nil, fmt.Errorf("line %d: %v", line, err)
		}
		wh, err := strconv.ParseInt(rec[2], 10, 64)
		if err != nil {
			return nil, fmt.Errorf("line %d: %v", line, err)
		}
		var fl uint64
		if len(rec) > 3 && rec[3] != "" {
			if fl, err = strconv.ParseUint(rec[3], 10, 8); err != nil {
				return nil, fmt.Errorf("line %d: %v", line, err)
			}
		}
		out = append(out, Reading{MeterID: rec[0], Start: t.UTC(), Wh: wh, Flags: Flags(fl)})
	}
}

// TotalWh sums the readings.
func TotalWh(rs []Reading) int64 {
	var s int64
	for _, r := range rs {
		s += r.Wh
	}
	return s
}
