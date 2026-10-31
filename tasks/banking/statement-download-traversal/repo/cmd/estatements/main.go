package main

import (
	"flag"
	"log"
	"net/http"
	"time"

	"github.com/northbank/estatements/internal/archive"
	"github.com/northbank/estatements/internal/audit"
	"github.com/northbank/estatements/internal/httpapi"
)

func main() {
	addr := flag.String("addr", ":8080", "listen address")
	root := flag.String("archive", "/srv/statements", "archive volume")
	flag.Parse()

	store := archive.New(*root)
	mux := http.NewServeMux()
	mux.Handle("/statements/download", &httpapi.Download{Store: store, Audit: audit.NewLog(nil)})
	mux.Handle("/statements", &httpapi.List{Store: store})
	srv := &http.Server{Addr: *addr, Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	log.Printf("estatements listening on %s (archive %s)", *addr, *root)
	log.Fatal(srv.ListenAndServe())
}
