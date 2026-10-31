#!/usr/bin/env bash
# Verifier for energy/tou-billing. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
cd "$WORKDIR" || exit 0
export PYTHONDONTWRITEBYTECODE=1
lib_run 120 "$SCRATCH/py.out" python3 .verifier/pyrunner.py \
  tests.test_billing tests.test_support tests.test_dst_and_rounding
lib_parse_result_lines "$SCRATCH/py.out"
