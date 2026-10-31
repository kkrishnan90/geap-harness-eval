#!/usr/bin/env bash
# Verifier for retail/promo-expiry-timezone. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
cd "$WORKDIR" || exit 0
export PYTHONDONTWRITEBYTECODE=1
lib_run 120 "$SCRATCH/py.out" python3 .verifier/pyrunner.py \
  tests.test_validity tests.test_pricing tests.test_coupons_reporting tests.test_validity_dst
lib_parse_result_lines "$SCRATCH/py.out"
