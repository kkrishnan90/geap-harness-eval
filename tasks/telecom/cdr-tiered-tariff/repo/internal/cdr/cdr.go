// Package cdr defines the correlated call detail record handed to rating.
package cdr

import (
	"encoding/csv"
	"errors"
	"fmt"
	"io"
	"strconv"
	"strings"
	"time"
)

// Record is one correlated voice call.
type Record struct {
	ID          string
	Subscriber  string    // charged party, E.164 (A-number for MO calls)
	Called      string    // B-number, E.164
	Start       time.Time // answer time if answered, else setup time
	DurationSec int64     // conversation time in whole seconds (0 if not answered)
	Answered    bool
}

// Header is the CSV column order produced by the correlation stage.
var Header = []string{"id", "subscriber", "called", "start", "duration_sec", "answered"}

// ParseCSV decodes records; the first line must be Header. Errors carry the line number.
func ParseCSV(r io.Reader) ([]Record, error) {
	cr := csv.NewReader(r)
	cr.FieldsPerRecord = len(Header)
	head, err := cr.Read()
	if err != nil {
		return nil, fmt.Errorf("cdr: header: %w", err)
	}
	if strings.Join(head, ",") != strings.Join(Header, ",") {
		return nil, errors.New("cdr: unexpected header")
	}
	var out []Record
	for line := 2; ; line++ {
		row, err := cr.Read()
		if err == io.EOF {
			return out, nil
		}
		if err != nil {
			return nil, fmt.Errorf("cdr: line %d: %w", line, err)
		}
		start, err := time.Parse(time.RFC3339, row[3])
		if err != nil {
			return nil, fmt.Errorf("cdr: line %d: start: %w", line, err)
		}
		dur, err := strconv.ParseInt(row[4], 10, 64)
		if err != nil || dur < 0 {
			return nil, fmt.Errorf("cdr: line %d: bad duration %q", line, row[4])
		}
		ans, err := strconv.ParseBool(row[5])
		if err != nil {
			return nil, fmt.Errorf("cdr: line %d: bad answered flag %q", line, row[5])
		}
		if !ans && dur != 0 {
			return nil, fmt.Errorf("cdr: line %d: unanswered call with duration", line)
		}
		out = append(out, Record{ID: row[0], Subscriber: row[1], Called: row[2], Start: start, DurationSec: dur, Answered: ans})
	}
}
