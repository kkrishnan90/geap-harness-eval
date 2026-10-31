// Package archive gives read-only access to the statement archive volume.
package archive

import (
	"errors"
	"io/fs"
	"os"
	"path/filepath"
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
func (s *Store) Open(name string) (*os.File, error) {
	if name == "" {
		return nil, ErrInvalidName
	}
	full := filepath.Join(s.Root, filepath.FromSlash(name))
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
