// Command vee-run validates a head-end CSV export for one day.
package main

import (
	"flag"
	"fmt"
	"os"
	"time"

	"grid.example/mdm/internal/interval"
	"grid.example/mdm/internal/vee"
)

func main() {
	day := flag.String("day", "", "UTC day, YYYY-MM-DD")
	flag.Parse()
	from, err := time.Parse("2006-01-02", *day)
	if err != nil || flag.NArg() != 1 {
		fmt.Fprintln(os.Stderr, "usage: vee-run -day YYYY-MM-DD export.csv")
		os.Exit(2)
	}
	f, err := os.Open(flag.Arg(0))
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	defer f.Close()
	rs, err := interval.DecodeCSV(f)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	cfg := vee.DefaultConfig()
	to := from.Add(24 * time.Hour)
	for _, is := range vee.Validate(rs, from, to, cfg) {
		fmt.Printf("%s %s\n", is.Start.Format(time.RFC3339), is.Code)
	}
	fmt.Printf("estimated %d slot(s)\n", len(vee.Estimate(rs, from, to, cfg)))
}
