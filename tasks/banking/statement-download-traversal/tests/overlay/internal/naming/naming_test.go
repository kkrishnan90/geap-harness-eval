package naming

import "testing"

func TestStatementName(t *testing.T) {
	got, err := StatementName("C1001", "de89 3704 0044 0532 0130 00", 2026, 3)
	if err != nil {
		t.Fatal(err)
	}
	if got != "C1001/2026/2026-03_DE89370400440532013000.pdf" {
		t.Fatalf("got %q", got)
	}
}

func TestStatementNameRejectsBadInput(t *testing.T) {
	cases := [][]any{
		{"1001", "DE89370400440532013000", 2026, 3},
		{"C1001", "DE89/../x", 2026, 3},
		{"C1001", "DE89370400440532013000", 2026, 13},
	}
	for _, c := range cases {
		if _, err := StatementName(c[0].(string), c[1].(string), c[2].(int), c[3].(int)); err == nil {
			t.Errorf("expected error for %v", c)
		}
	}
}

func TestDownloadFilename(t *testing.T) {
	if got := DownloadFilename("C1001/2026/2026-03_X.pdf"); got != "statement_2026-03_X.pdf" {
		t.Fatalf("got %q", got)
	}
}
