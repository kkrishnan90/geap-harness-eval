package rating

import (
	"fmt"
	"strconv"
	"strings"
)

// Increment is a billing increment pair in seconds, written "initial/subsequent"
// (e.g. "60/60" per-minute, "30/6", "1/1" per-second).
type Increment struct {
	Initial    int64
	Subsequent int64
}

// ParseIncrement parses "initial/subsequent"; both must be positive integers.
func ParseIncrement(s string) (Increment, error) {
	a, b, ok := strings.Cut(strings.TrimSpace(s), "/")
	if !ok {
		return Increment{}, fmt.Errorf("rating: bad increment %q", s)
	}
	i, err1 := strconv.ParseInt(a, 10, 64)
	n, err2 := strconv.ParseInt(b, 10, 64)
	if err1 != nil || err2 != nil || i <= 0 || n <= 0 {
		return Increment{}, fmt.Errorf("rating: bad increment %q", s)
	}
	return Increment{Initial: i, Subsequent: n}, nil
}

// Billable rounds a conversation duration up to the increments.
func (inc Increment) Billable(durationSec int64) int64 {
	if durationSec <= 0 {
		return 0
	}
	if durationSec <= inc.Initial {
		return inc.Initial
	}
	rest := durationSec - inc.Initial
	steps := (rest + inc.Subsequent - 1) / inc.Subsequent
	return inc.Initial + steps*inc.Subsequent
}

// String formats as "initial/subsequent".
func (inc Increment) String() string {
	return fmt.Sprintf("%d/%d", inc.Initial, inc.Subsequent)
}
