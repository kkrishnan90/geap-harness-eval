// Command quota-sim validates a slice policy file and prints the effective
// quotas. (Trace replay will be added once the limiter lands, PCF-2210.)
package main

import (
	"flag"
	"fmt"
	"os"

	"telco.example/pcf-quota/internal/policy"
)

func main() {
	path := flag.String("policy", "configs/slices.json", "slice policy JSON")
	flag.Parse()
	specs, err := policy.LoadFile(*path)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	for _, s := range specs {
		fmt.Printf("%-10s aggregate %d/s burst %d, per-subscriber %d/s burst %d\n",
			s.Slice, s.Aggregate.RatePerSec, s.Aggregate.Burst, s.PerSubscriber.RatePerSec, s.PerSubscriber.Burst)
	}
}
