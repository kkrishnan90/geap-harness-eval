"""python3 -m policy [--json] [--env ENV ...] <deploy_root>"""

import argparse
import sys

from .loader import ENVIRONMENTS, ManifestError, load_env, load_lock
from .report import as_json, as_text
from .rules import Violation, check_env


def main(argv=None):
    ap = argparse.ArgumentParser(prog="policy")
    ap.add_argument("root")
    ap.add_argument("--env", action="append", choices=ENVIRONMENTS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    lock = load_lock(args.root)
    violations = []
    for env in args.env or ENVIRONMENTS:
        try:
            manifests = load_env(args.root, env)
        except ManifestError as e:
            violations.append(Violation(env, "P000", env, str(e)))
            continue
        violations.extend(check_env(env, manifests, lock))
    print(as_json(violations) if args.json else as_text(violations))
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
