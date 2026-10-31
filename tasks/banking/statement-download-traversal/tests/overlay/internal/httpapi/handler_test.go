package httpapi

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"testing"

	"github.com/northbank/estatements/internal/archive"
	"github.com/northbank/estatements/internal/audit"
)

func newHandler(t *testing.T) (*Download, string) {
	t.Helper()
	root := t.TempDir()
	for name, body := range map[string]string{
		"C1001/2026/2026-03_DE89370400440532013000.pdf":       "%PDF-1.7 mine",
		"C2002/2026/2026-03_FR1420041010050500013M02606.pdf": "%PDF-1.7 theirs",
	} {
		p := filepath.Join(root, filepath.FromSlash(name))
		os.MkdirAll(filepath.Dir(p), 0o755)
		if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return &Download{Store: archive.New(root), Audit: audit.NewLog(nil)}, root
}

func get(h http.Handler, customer, file string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodGet, "/statements/download?file="+url.QueryEscape(file), nil)
	if customer != "" {
		req.Header.Set(CustomerHeader, customer)
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func TestDownloadOwnStatement(t *testing.T) {
	h, _ := newHandler(t)
	rec := get(h, "C1001", "C1001/2026/2026-03_DE89370400440532013000.pdf")
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d", rec.Code)
	}
	if rec.Body.String() != "%PDF-1.7 mine" {
		t.Fatalf("body %q", rec.Body.String())
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/pdf" {
		t.Fatalf("content type %q", ct)
	}
	if cd := rec.Header().Get("Content-Disposition"); cd != `attachment; filename="statement_2026-03_DE89370400440532013000.pdf"` {
		t.Fatalf("disposition %q", cd)
	}
}

func TestDownloadOtherCustomerForbidden(t *testing.T) {
	h, _ := newHandler(t)
	if rec := get(h, "C1001", "C2002/2026/2026-03_FR1420041010050500013M02606.pdf"); rec.Code != http.StatusForbidden {
		t.Fatalf("status %d", rec.Code)
	}
}

func TestDownloadUnauthenticated(t *testing.T) {
	h, _ := newHandler(t)
	if rec := get(h, "", "C1001/2026/2026-03_DE89370400440532013000.pdf"); rec.Code != http.StatusUnauthorized {
		t.Fatalf("status %d", rec.Code)
	}
}

func TestDownloadMissing(t *testing.T) {
	h, _ := newHandler(t)
	if rec := get(h, "C1001", "C1001/2026/2026-01_DE89370400440532013000.pdf"); rec.Code != http.StatusNotFound {
		t.Fatalf("status %d", rec.Code)
	}
}

func TestDownloadMethodNotAllowed(t *testing.T) {
	h, _ := newHandler(t)
	req := httptest.NewRequest(http.MethodPost, "/statements/download?file=x", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("status %d", rec.Code)
	}
}

func TestDownloadIsAudited(t *testing.T) {
	h, _ := newHandler(t)
	get(h, "C1001", "C1001/2026/2026-03_DE89370400440532013000.pdf")
	get(h, "C1001", "C2002/x.pdf")
	e := h.Audit.Entries()
	if len(e) != 2 || e[0].Status != 200 || e[1].Status != 403 || e[1].Name != "C2002/x.pdf" {
		t.Fatalf("audit %+v", e)
	}
}
