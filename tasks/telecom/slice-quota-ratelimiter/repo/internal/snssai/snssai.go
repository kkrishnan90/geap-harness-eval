// Package snssai implements the Single Network Slice Selection Assistance
// Information identifier: an 8-bit Slice/Service Type plus optional 24-bit
// Slice Differentiator.
package snssai

import (
	"fmt"
	"strconv"
	"strings"
)

// NoSD is the reserved "no slice differentiator" value.
const NoSD uint32 = 0xFFFFFF

// SNSSAI is comparable and can be used as a map key.
type SNSSAI struct {
	SST uint8
	SD  uint32 // 24 bit; NoSD when absent
}

// Standardised SST values (TS 23.501 §5.15.2.2).
const (
	SSTeMBB  uint8 = 1
	SSTURLLC uint8 = 2
	SSTMIoT  uint8 = 3
	SSTV2X   uint8 = 4
)

// New builds an S-NSSAI. sd must fit in 24 bits.
func New(sst uint8, sd uint32) (SNSSAI, error) {
	if sd > 0xFFFFFF {
		return SNSSAI{}, fmt.Errorf("snssai: SD %#x exceeds 24 bits", sd)
	}
	return SNSSAI{SST: sst, SD: sd}, nil
}

// MustParse is Parse for constants in tests and config defaults.
func MustParse(s string) SNSSAI {
	v, err := Parse(s)
	if err != nil {
		panic(err)
	}
	return v
}

// Parse accepts "SST" or "SST-SD" with SST decimal (0-255) and SD as 6 hex digits.
func Parse(s string) (SNSSAI, error) {
	s = strings.TrimSpace(s)
	sstPart, sdPart, hasSD := strings.Cut(s, "-")
	sst, err := strconv.ParseUint(sstPart, 10, 8)
	if err != nil {
		return SNSSAI{}, fmt.Errorf("snssai: bad SST in %q", s)
	}
	if !hasSD {
		return SNSSAI{SST: uint8(sst), SD: NoSD}, nil
	}
	if len(sdPart) != 6 {
		return SNSSAI{}, fmt.Errorf("snssai: SD must be 6 hex digits in %q", s)
	}
	sd, err := strconv.ParseUint(sdPart, 16, 32)
	if err != nil {
		return SNSSAI{}, fmt.Errorf("snssai: bad SD in %q", s)
	}
	return SNSSAI{SST: uint8(sst), SD: uint32(sd)}, nil
}

// String renders "SST" or "SST-sd" (lower-case hex), the inverse of Parse.
func (n SNSSAI) String() string {
	if n.SD == NoSD {
		return strconv.Itoa(int(n.SST))
	}
	return fmt.Sprintf("%d-%06x", n.SST, n.SD)
}
