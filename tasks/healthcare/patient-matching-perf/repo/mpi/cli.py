"""Command line entry point: python3 -m mpi.cli link records.csv [-o matches.csv]"""

import argparse
import json
import sys

from .io_csv import read_records, write_matches
from .linker import clusters, link
from .report import worklist_summary
from .scoring import PairScorer


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mpi")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("link")
    p.add_argument("records")
    p.add_argument("-o", "--output")
    args = ap.parse_args(argv)
    records = read_records(args.records)
    scorer = PairScorer()
    matches = link(records, scorer)
    if args.output:
        write_matches(args.output, matches)
    summary = worklist_summary(records, clusters(records, matches))
    summary["comparisons"] = scorer.comparisons
    json.dump(summary, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
