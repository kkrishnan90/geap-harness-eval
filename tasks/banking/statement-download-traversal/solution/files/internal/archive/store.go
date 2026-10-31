// Package archive gives read-only access to the statement archive volume.
package archive

import (
	"errors"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
)

var (
	// ErrNotFound is returned when no statement exists under the given name.
	ErrNotFound = errors.New("archive: statement not found")
	// ErrInvalidName is returned for names that are not valid archive names.
	ErrInvalidName = errors.New("archive: invalid statement name")
)

// Store reads statements below Root.
type Store struct {
	Root string
}

// New returns a Store rooted at dir.
func New(dir string) *Store {
	return &Store{Root: dir}
}

// Open opens the statement stored under name, a slash-separated path relative
// to the archive root such as "C1001/2026/2026-03_DE89370400440532013000.pdf".
// The caller must Close the returned file.
//
// Names that are absolute, contain empty, "." or ".." segments, backslashes or
// NUL bytes are rejected with ErrInvalidName, as are names that resolve (via
// symlinks) to a location outside the archive root.
func (s *Store) Open(name string) (*os.File, error) {
	if !validName(name) {
		return nil, ErrInvalidName
	}
	rootReal, err := filepath.EvalSymlinks(s.Root)
	if err != nil {
		if errors.Is(err, fs.ErrNotExist) {
			return nil, ErrNotFound
		}
		return nil, err
	}
	full, err := filepath.EvalSymlinks(filepath.Join(rootReal, filepath.FromSlash(name)))
	if err != nil {
		if errors.Is(err, fs.ErrNotExist) {
			return nil, ErrNotFound
		}
		return nil, err
	}
	if !within(rootReal, full) {
		return nil, ErrInvalidName
	}
	f, err := os.Open(full)
	if err != nil {
		if errors.Is(err, fs.ErrNotExist) {
			return nil, ErrNotFound
		}
		return nil, err
	}
	st, err := f.Stat()
	if err != nil {
		f.Close()
		return nil, err
	}
	if st.IsDir() {
		f.Close()
		return nil, ErrNotFound
	}
	return f, nil
}

func validName(name string) bool {
	if name == "" || strings.HasPrefix(name, "/") || strings.ContainsAny(name, "\\\x00") {
		return false
	}
	for _, seg := range strings.Split(name, "/") {
		if seg == "" || seg == "." || seg == ".." {
			return false
		}
	}
	return true
}

func within(root, p string) bool {
	rel, err := filepath.Rel(root, p)
	if err != nil {
		return false
	}
	return rel != ".." && !strings.HasPrefix(rel, ".."+string(filepath.Separator)) && !filepath.IsAbs(rel)
}

// List returns the statement names (slash-separated, relative to Root) in a
// customer's directory, in lexical order.
func (s *Store) List(customer string) ([]string, error) {
	if customer == "" || customer != filepath.Base(customer) || customer == "." || customer == ".." {
		return nil, ErrInvalidName
	}
	base := filepath.Join(s.Root, customer)
	var names []string
	err := filepath.WalkDir(base, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.Type().IsRegular() && filepath.Ext(p) == ".pdf" {
			rel, rerr := filepath.Rel(s.Root, p)
			if rerr != nil {
				return rerr
			}
			names = append(names, filepath.ToSlash(rel))
		}
		return nil
	})
	if errors.Is(err, fs.ErrNotExist) {
		return nil, nil
	}
	return names, err
}
