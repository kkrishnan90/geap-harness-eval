package money

import (
	"errors"
	"testing"
)

func TestMoneyParseAndString(t *testing.T) {
	cases := map[string]string{"12": "12.0000", "0.09": "0.0900", "-0.5": "-0.5000", "+3.1415": "3.1415", "0": "0.0000"}
	for in, want := range cases {
		m, err := Parse(in)
		if err != nil {
			t.Fatalf("%s: %v", in, err)
		}
		if m.String() != want {
			t.Errorf("%s -> %s, want %s", in, m, want)
		}
	}
	for _, bad := range []string{"", "1.", ".5", "1.23456", "1,5", "abc", "--1"} {
		if _, err := Parse(bad); !errors.Is(err, ErrSyntax) {
			t.Errorf("%q: expected ErrSyntax, got %v", bad, err)
		}
	}
}

func TestMoneyDivRoundHalfUp(t *testing.T) {
	cases := []struct{ n, d, want int64 }{{5, 2, 3}, {4, 2, 2}, {7, 3, 2}, {-5, 2, -3}, {-7, 3, -2}, {1, 60, 0}, {30, 60, 1}}
	for _, c := range cases {
		if got := DivRoundHalfUp(c.n, c.d); got != c.want {
			t.Errorf("%d/%d = %d, want %d", c.n, c.d, got, c.want)
		}
	}
}

func TestMoneyPerMinute(t *testing.T) {
	// 0.0350/min for 61 s = 0.0355833.. -> 0.0356
	if got := PerMinute(MustParse("0.0350"), 61); got.String() != "0.0356" {
		t.Fatalf("got %s", got)
	}
}
