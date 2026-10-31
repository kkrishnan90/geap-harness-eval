#!/usr/bin/env bash
# Verifier for banking/iban-checksum-bug. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
cd "$WORKDIR" || exit 0
export PYTHONDONTWRITEBYTECODE=1
lib_run 120 "$SCRATCH/py.out" python3 .verifier/pyrunner.py \
  tests.test_iban tests.test_bic tests.test_sepa tests.test_iban_input_forms
lib_parse_result_lines "$SCRATCH/py.out"
