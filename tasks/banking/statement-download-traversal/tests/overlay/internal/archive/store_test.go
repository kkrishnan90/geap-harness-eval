package archive

import (
	"errors"
	"io"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func newFixture(t *testing.T) *Store {
	t.Helper()
	root := t.TempDir()
	files := map[string]string{
		"C1001/2026/2026-02_DE89370400440532013000.pdf": "%PDF-1.7 feb",
		"C1001/2026/2026-03_DE89370400440532013000.pdf": "%PDF-1.7 mar",
		"C2002/2026/2026-03_FR1420041010050500013M02606.pdf": "%PDF-1.7 other",
	}
	for name, body := range files {
		p := filepath.Join(root, filepath.FromSlash(name))
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return New(root)
}

func TestOpenNestedStatement(t *testing.T) {
	s := newFixture(t)
	f, err := s.Open("C1001/2026/2026-03_DE89370400440532013000.pdf")
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	defer f.Close()
	b, _ := io.ReadAll(f)
	if string(b) != "%PDF-1.7 mar" {
		t.Fatalf("got %q", b)
	}
}

func TestOpenMissing(t *testing.T) {
	s := newFixture(t)
	if _, err := s.Open("C1001/2026/2026-04_DE89370400440532013000.pdf"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("want ErrNotFound, got %v", err)
	}
}

func TestOpenDirectoryIsNotFound(t *testing.T) {
	s := newFixture(t)
	if _, err := s.Open("C1001/2026"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("want ErrNotFound, got %v", err)
	}
}

func TestOpenEmptyName(t *testing.T) {
	if _, err := newFixture(t).Open(""); !errors.Is(err, ErrInvalidName) {
		t.Fatalf("want ErrInvalidName, got %v", err)
	}
}

func TestListCustomer(t *testing.T) {
	got, err := newFixture(t).List("C1001")
	if err != nil {
		t.Fatal(err)
	}
	want := []string{
		"C1001/2026/2026-02_DE89370400440532013000.pdf",
		"C1001/2026/2026-03_DE89370400440532013000.pdf",
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v", got)
	}
}

func TestListRejectsTraversal(t *testing.T) {
	if _, err := newFixture(t).List(".."); !errors.Is(err, ErrInvalidName) {
		t.Fatalf("want ErrInvalidName, got %v", err)
	}
}
