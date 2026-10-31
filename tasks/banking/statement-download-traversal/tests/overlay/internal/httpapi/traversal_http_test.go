package httpapi

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/northbank/estatements/internal/archive"
	"github.com/northbank/estatements/internal/audit"
)

func newTraversalHandler(t *testing.T) (*Download, string) {
	t.Helper()
	tmp := t.TempDir()
	root := filepath.Join(tmp, "archive")
	for name, body := range map[string]string{
		"archive/C1001/2026/2026-03_DE89370400440532013000.pdf":       "%PDF-1.7 mine",
		"archive/C2002/2026/2026-03_FR1420041010050500013M02606.pdf": "%PDF-1.7 theirs",
		"secret.txt": "db_password=hunter2",
	} {
		p := filepath.Join(tmp, filepath.FromSlash(name))
		os.MkdirAll(filepath.Dir(p), 0o755)
		if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return &Download{Store: archive.New(root), Audit: audit.NewLog(nil)}, root
}

func rawGet(h http.Handler, customer, rawQuery string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodGet, "/statements/download?"+rawQuery, nil)
	req.Header.Set(CustomerHeader, customer)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func TestDownloadPrefixCheckBypass(t *testing.T) {
	h, _ := newTraversalHandler(t)
	rec := rawGet(h, "C1001", "file=C1001/../C2002/2026/2026-03_FR1420041010050500013M02606.pdf")
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status %d body %q, want 400", rec.Code, rec.Body.String())
	}
	if strings.Contains(rec.Body.String(), "theirs") {
		t.Fatal("served another customer's statement")
	}
}

func TestDownloadEncodedTraversal(t *testing.T) {
	h, root := newTraversalHandler(t)
	for _, q := range []string{
		"file=C1001%2F..%2F..%2Fsecret.txt",
		"file=C1001/%2e%2e/%2e%2e/secret.txt",
		"file=C1001/%2E%2E/%2E%2E/secret.txt",
		"file=C1001/2026/..%2F..%2F..%2Fsecret.txt",
	} {
		rec := rawGet(h, "C1001", q)
		if rec.Code != http.StatusBadRequest {
			t.Errorf("%s: status %d body %q, want 400", q, rec.Code, rec.Body.String())
		}
		if strings.Contains(rec.Body.String(), "hunter2") || strings.Contains(rec.Body.String(), root) {
			t.Errorf("%s: leaked data or path: %q", q, rec.Body.String())
		}
	}
}

func TestDownloadDoubleEncodedIsJustNotFound(t *testing.T) {
	h, _ := newTraversalHandler(t)
	rec := rawGet(h, "C1001", "file=C1001%2F%252e%252e%2F%252e%252e%2Fsecret.txt")
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status %d, want 404", rec.Code)
	}
}

func TestDownloadTraversalAudited(t *testing.T) {
	h, _ := newTraversalHandler(t)
	rawGet(h, "C1001", "file=C1001/../../secret.txt")
	e := h.Audit.Entries()
	if len(e) != 1 || e[0].Status != http.StatusBadRequest || e[0].Name != "C1001/../../secret.txt" {
		t.Fatalf("audit %+v", e)
	}
}

func TestDownloadStillServesOwnStatement(t *testing.T) {
	h, _ := newTraversalHandler(t)
	rec := rawGet(h, "C1001", "file=C1001%2F2026%2F2026-03_DE89370400440532013000.pdf")
	if rec.Code != http.StatusOK || rec.Body.String() != "%PDF-1.7 mine" {
		t.Fatalf("status %d body %q", rec.Code, rec.Body.String())
	}
}
