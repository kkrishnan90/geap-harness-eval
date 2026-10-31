// Package obis parses OBIS codes such as "1-0:1.8.0*255".
package obis

import (
	"fmt"
	"strconv"
	"strings"
)

// Code is an OBIS identifier A-B:C.D.E*F.
type Code [6]uint8

// Parse accepts "A-B:C.D.E*F" or the short form "C.D.E" (A=1,B=0,F=255).
func Parse(s string) (Code, error) {
	s = strings.TrimSpace(s)
	var c Code
	c[0], c[1], c[5] = 1, 0, 255
	rest := s
	if a, after, ok := strings.Cut(rest, "-"); ok {
		v, err := strconv.ParseUint(a, 10, 8)
		if err != nil {
			return c, fmt.Errorf("obis: bad A in %q", s)
		}
		c[0] = uint8(v)
		b, after2, ok := strings.Cut(after, ":")
		if !ok {
			return c, fmt.Errorf("obis: missing ':' in %q", s)
		}
		v, err = strconv.ParseUint(b, 10, 8)
		if err != nil {
			return c, fmt.Errorf("obis: bad B in %q", s)
		}
		c[1] = uint8(v)
		rest = after2
	}
	if body, f, ok := strings.Cut(rest, "*"); ok {
		v, err := strconv.ParseUint(f, 10, 8)
		if err != nil {
			return c, fmt.Errorf("obis: bad F in %q", s)
		}
		c[5] = uint8(v)
		rest = body
	}
	parts := strings.Split(rest, ".")
	if len(parts) != 3 {
		return c, fmt.Errorf("obis: want C.D.E in %q", s)
	}
	for i, p := range parts {
		v, err := strconv.ParseUint(p, 10, 8)
		if err != nil {
			return c, fmt.Errorf("obis: bad group in %q", s)
		}
		c[2+i] = uint8(v)
	}
	return c, nil
}

func (c Code) String() string {
	return fmt.Sprintf("%d-%d:%d.%d.%d*%d", c[0], c[1], c[2], c[3], c[4], c[5])
}

// IsActiveImport reports whether the code is active energy import (C=1, D=8).
func (c Code) IsActiveImport() bool { return c[2] == 1 && c[3] == 8 }
