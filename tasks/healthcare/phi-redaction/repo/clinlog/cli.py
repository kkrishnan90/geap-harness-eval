"""Command line entry point.

    python3 -m clinlog sanitize [--config clinlog.ini] < raw.log > clean.log
    python3 -m clinlog stats    [--config clinlog.ini] < raw.log
"""

import argparse
import sys

from .config import load_config
from .pipeline import Pipeline


def _parser():
    p = argparse.ArgumentParser(prog="clinlog")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("sanitize", help="redact PHI from stdin to stdout")
    s.add_argument("--config", help="INI file with a [clinlog] section")
    st = sub.add_parser("stats", help="print line counters for stdin")
    st.add_argument("--config")
    return p


def main(argv=None, stdin=None, stdout=None) -> int:
    args = _parser().parse_args(argv)
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    config = load_config(args.config) if args.config else load_config()
    pipeline = Pipeline(config)
    if args.command == "sanitize":
        for line in pipeline.process(stdin):
            stdout.write(line + "\n")
    else:
        for _ in pipeline.process(stdin):
            pass
        stdout.write(pipeline.metrics.render())
    return 0
