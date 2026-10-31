"""Command line entry point: python3 -m prmrate.cli INPUT OUTPUT"""

import sys

from .batch import run_batch


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: python3 -m prmrate.cli INPUT OUTPUT", file=sys.stderr)
        return 2
    with open(argv[0], encoding="ascii", newline="") as f:
        lines = f.read().splitlines()
    out = run_batch(lines)
    with open(argv[1], "w", encoding="ascii", newline="\n") as f:
        for line in out:
            f.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
