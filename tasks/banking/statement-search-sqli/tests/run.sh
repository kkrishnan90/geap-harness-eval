#!/usr/bin/env bash
# Verifier for banking/statement-search-sqli. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
cd "$WORKDIR" || exit 0
export PYTHONDONTWRITEBYTECODE=1
lib_run 120 "$SCRATCH/py.out" python3 .verifier/pyrunner.py \
  tests.test_search tests.test_api tests.test_statements \
  tests.test_search_injection tests.test_api_injection
lib_parse_result_lines "$SCRATCH/py.out"
