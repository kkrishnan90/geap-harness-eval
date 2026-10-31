// Command rater prices a CDR CSV from stdin with a flat plan and prints rated lines.
package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/telcoridge/mediation/internal/cdr"
	"github.com/telcoridge/mediation/internal/money"
	"github.com/telcoridge/mediation/internal/rating"
)

func main() {
	planPath := flag.String("plan", "testdata/flat.json", "flat tariff file")
	flag.Parse()
	f, err := os.Open(*planPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	defer f.Close()
	plan, err := rating.LoadFlatPlan(f)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	recs, err := cdr.ParseCSV(os.Stdin)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	var total money.Money
	for _, r := range recs {
		amt, err := rating.RateFlat(r, plan)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", r.ID, err)
			continue
		}
		total += amt
		fmt.Printf("%s,%s,%d,%s\n", r.ID, r.Subscriber, r.DurationSec, amt)
	}
	fmt.Printf("TOTAL,%s\n", total)
}
