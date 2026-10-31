#!/usr/bin/env bash
# CI entrypoint: lint, then the full unit test suite.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== lint"
python3 tools/lint.py src tests tools

echo "== unit tests"
PYTHONPATH=src python3 -m unittest discover -s tests -t . -p 'test*.py' -v
