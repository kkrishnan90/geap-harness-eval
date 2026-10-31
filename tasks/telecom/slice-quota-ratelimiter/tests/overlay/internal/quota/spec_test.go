package quota

import (
	"errors"
	"testing"

	"telco.example/pcf-quota/internal/snssai"
)

func goodSpec(s string) SliceSpec {
	return SliceSpec{
		Slice:         snssai.MustParse(s),
		Aggregate:     BucketSpec{RatePerSec: 1000, Burst: 5000},
		PerSubscriber: BucketSpec{RatePerSec: 100, Burst: 500},
	}
}

func TestSpecValidateOK(t *testing.T) {
	if err := ValidateAll([]SliceSpec{goodSpec("1-000001"), goodSpec("2")}); err != nil {
		t.Fatal(err)
	}
}

func TestSpecValidateRejectsZeroRate(t *testing.T) {
	s := goodSpec("1")
	s.PerSubscriber.RatePerSec = 0
	if err := s.Validate(); !errors.Is(err, ErrInvalidSpec) {
		t.Fatalf("got %v", err)
	}
}

func TestSpecValidateRejectsDuplicate(t *testing.T) {
	err := ValidateAll([]SliceSpec{goodSpec("1-000001"), goodSpec("1-000001")})
	if !errors.Is(err, ErrInvalidSpec) {
		t.Fatalf("got %v", err)
	}
}
