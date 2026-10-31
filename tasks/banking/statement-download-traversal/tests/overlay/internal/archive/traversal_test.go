package archive

import (
	"errors"
	"io"
	"os"
	"path/filepath"
	"testing"
)

// layout: <tmp>/secret.pdf (outside), <tmp>/archive/... (root)
func newTraversalFixture(t *testing.T) (*Store, string) {
	t.Helper()
	tmp := t.TempDir()
	root := filepath.Join(tmp, "archive")
	write := func(p, body string) {
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	write(filepath.Join(tmp, "secret.pdf"), "TOP SECRET")
	write(filepath.Join(tmp, "outside", "keys.pdf"), "KEYS")
	write(filepath.Join(root, "C1001", "2026", "2026-03_DE89370400440532013000.pdf"), "%PDF mine")
	write(filepath.Join(root, "C1001", "2026", "2026-03..pdf"), "%PDF dots")
	write(filepath.Join(root, "C2002", "2026", "2026-03_FR1420041010050500013M02606.pdf"), "%PDF theirs")
	return New(root), tmp
}

func mustReject(t *testing.T, s *Store, name string) {
	t.Helper()
	f, err := s.Open(name)
	if err == nil {
		b, _ := io.ReadAll(f)
		f.Close()
		t.Errorf("Open(%q) succeeded (read %q), want ErrInvalidName", name, b)
		return
	}
	if !errors.Is(err, ErrInvalidName) {
		t.Errorf("Open(%q) = %v, want ErrInvalidName", name, err)
	}
}

func TestOpenRejectsParentSegments(t *testing.T) {
	s, _ := newTraversalFixture(t)
	for _, name := range []string{
		"../secret.pdf",
		"C1001/../../secret.pdf",
		"C1001/2026/../../../secret.pdf",
		"C1001/2026/../../C2002/2026/2026-03_FR1420041010050500013M02606.pdf",
		"..",
		"C1001/..",
	} {
		mustReject(t, s, name)
	}
}

func TestOpenRejectsAbsoluteNames(t *testing.T) {
	s, tmp := newTraversalFixture(t)
	mustReject(t, s, "/etc/passwd")
	mustReject(t, s, filepath.ToSlash(filepath.Join(tmp, "secret.pdf")))
}

func TestOpenRejectsMalformedNames(t *testing.T) {
	s, _ := newTraversalFixture(t)
	for _, name := range []string{
		"C1001\\..\\..\\secret.pdf",
		"C1001/2026/2026-03_DE89370400440532013000.pdf\x00.txt",
		"C1001//2026/2026-03_DE89370400440532013000.pdf",
		"C1001/./2026/2026-03_DE89370400440532013000.pdf",
		"./C1001/2026/2026-03_DE89370400440532013000.pdf",
		"C1001/2026/",
	} {
		mustReject(t, s, name)
	}
}

func TestOpenRejectsSymlinkEscape(t *testing.T) {
	s, tmp := newTraversalFixture(t)
	if err := os.Symlink(filepath.Join(tmp, "secret.pdf"), filepath.Join(s.Root, "C1001", "2026", "2026-04_link.pdf")); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(filepath.Join(tmp, "outside"), filepath.Join(s.Root, "C1001", "shared")); err != nil {
		t.Fatal(err)
	}
	mustReject(t, s, "C1001/2026/2026-04_link.pdf")
	mustReject(t, s, "C1001/shared/keys.pdf")
}

func TestOpenAllowsInternalSymlinkAndDottedFileNames(t *testing.T) {
	s, _ := newTraversalFixture(t)
	if err := os.Symlink(filepath.Join(s.Root, "C1001", "2026", "2026-03_DE89370400440532013000.pdf"),
		filepath.Join(s.Root, "C1001", "2026", "latest.pdf")); err != nil {
		t.Fatal(err)
	}
	for name, want := range map[string]string{
		"C1001/2026/latest.pdf":    "%PDF mine",
		"C1001/2026/2026-03..pdf": "%PDF dots",
	} {
		f, err := s.Open(name)
		if err != nil {
			t.Errorf("Open(%q): %v", name, err)
			continue
		}
		b, _ := io.ReadAll(f)
		f.Close()
		if string(b) != want {
			t.Errorf("Open(%q) read %q", name, b)
		}
	}
}

func TestOpenThroughSymlinkedRoot(t *testing.T) {
	s, tmp := newTraversalFixture(t)
	link := filepath.Join(tmp, "archive-current")
	if err := os.Symlink(s.Root, link); err != nil {
		t.Fatal(err)
	}
	f, err := New(link).Open("C1001/2026/2026-03_DE89370400440532013000.pdf")
	if err != nil {
		t.Fatalf("Open via symlinked root: %v", err)
	}
	f.Close()
	if _, err := New(link).Open("C1001/2026/2026-05_DE89370400440532013000.pdf"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("missing file via symlinked root: %v", err)
	}
}
