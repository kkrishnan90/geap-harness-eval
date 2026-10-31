// Package money implements fixed-point currency amounts with 4 decimal places.
package money

import (
	"errors"
	"fmt"
	"strconv"
	"strings"
)

// Money is an amount in 1/10000 of the currency unit (e.g. 0.0001 EUR).
type Money int64

// Scale is the number of Money units per currency unit.
const Scale = 10000

// ErrSyntax is returned for malformed amounts.
var ErrSyntax = errors.New("money: invalid amount")

// Parse reads a decimal string with at most 4 fractional digits ("12", "-0.5", "0.0900").
func Parse(s string) (Money, error) {
	s = strings.TrimSpace(s)
	if s == "" {
		return 0, ErrSyntax
	}
	neg := false
	if s[0] == '-' || s[0] == '+' {
		neg = s[0] == '-'
		s = s[1:]
	}
	whole, frac, hasDot := strings.Cut(s, ".")
	if whole == "" || (hasDot && frac == "") || len(frac) > 4 {
		return 0, fmt.Errorf("%w: %q", ErrSyntax, s)
	}
	for _, part := range []string{whole, frac} {
		for _, c := range part {
			if c < '0' || c > '9' {
				return 0, fmt.Errorf("%w: %q", ErrSyntax, s)
			}
		}
	}
	w, err := strconv.ParseInt(whole, 10, 64)
	if err != nil || w > (1<<62)/Scale {
		return 0, fmt.Errorf("%w: %q", ErrSyntax, s)
	}
	frac = (frac + "0000")[:4]
	f, _ := strconv.ParseInt(frac, 10, 64)
	v := Money(w*Scale + f)
	if neg {
		v = -v
	}
	return v, nil
}

// MustParse is Parse for constants; it panics on error.
func MustParse(s string) Money {
	m, err := Parse(s)
	if err != nil {
		panic(err)
	}
	return m
}

// String formats with exactly 4 decimals.
func (m Money) String() string {
	sign := ""
	v := int64(m)
	if v < 0 {
		sign = "-"
		v = -v
	}
	return fmt.Sprintf("%s%d.%04d", sign, v/Scale, v%Scale)
}

// DivRoundHalfUp returns num/den rounded half away from zero. den must be > 0.
func DivRoundHalfUp(num, den int64) int64 {
	if den <= 0 {
		panic("money: non-positive divisor")
	}
	q, r := num/den, num%den
	if r < 0 {
		r = -r
	}
	if 2*r >= den {
		if num < 0 {
			q--
		} else {
			q++
		}
	}
	return q
}

// PerMinute prices seconds of usage at a per-minute rate, rounded half-up.
func PerMinute(rate Money, seconds int64) Money {
	return Money(DivRoundHalfUp(int64(rate)*seconds, 60))
}
