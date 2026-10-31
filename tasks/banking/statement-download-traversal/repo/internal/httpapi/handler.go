// Package httpapi contains the HTTP handlers of the estatements service.
package httpapi

import (
	"errors"
	"io"
	"log"
	"net/http"
	"strings"

	"github.com/northbank/estatements/internal/archive"
	"github.com/northbank/estatements/internal/audit"
	"github.com/northbank/estatements/internal/naming"
)

// CustomerHeader carries the authenticated customer id (set by the gateway).
const CustomerHeader = "X-Customer-ID"

// Download serves GET /statements/download?file=<archive name>.
type Download struct {
	Store *archive.Store
	Audit *audit.Log
}

func (h *Download) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		w.Header().Set("Allow", http.MethodGet)
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	customer := r.Header.Get(CustomerHeader)
	name := r.URL.Query().Get("file")
	status := h.serve(w, customer, name)
	if h.Audit != nil {
		h.Audit.Record(customer, name, status)
	}
}

func (h *Download) serve(w http.ResponseWriter, customer, name string) int {
	if customer == "" {
		http.Error(w, "unauthenticated", http.StatusUnauthorized)
		return http.StatusUnauthorized
	}
	if !strings.HasPrefix(name, customer+"/") {
		http.Error(w, "forbidden", http.StatusForbidden)
		return http.StatusForbidden
	}
	f, err := h.Store.Open(name)
	switch {
	case errors.Is(err, archive.ErrInvalidName):
		http.Error(w, "invalid statement name", http.StatusBadRequest)
		return http.StatusBadRequest
	case errors.Is(err, archive.ErrNotFound):
		http.Error(w, "statement not found", http.StatusNotFound)
		return http.StatusNotFound
	case err != nil:
		log.Printf("estatements: open failed: %v", err)
		http.Error(w, "internal error", http.StatusInternalServerError)
		return http.StatusInternalServerError
	}
	defer f.Close()
	w.Header().Set("Content-Type", "application/pdf")
	w.Header().Set("Content-Disposition", `attachment; filename="`+naming.DownloadFilename(name)+`"`)
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(http.StatusOK)
	if _, err := io.Copy(w, f); err != nil {
		log.Printf("estatements: copy failed: %v", err)
	}
	return http.StatusOK
}

// List serves GET /statements returning one archive name per line.
type List struct {
	Store *archive.Store
}

func (h *List) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	customer := r.Header.Get(CustomerHeader)
	if customer == "" {
		http.Error(w, "unauthenticated", http.StatusUnauthorized)
		return
	}
	names, err := h.Store.List(customer)
	if err != nil {
		http.Error(w, "invalid customer", http.StatusBadRequest)
		return
	}
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	for _, n := range names {
		io.WriteString(w, n+"\n")
	}
}
