#!/usr/bin/env bash
# Verifier for insurance/fixed-width-rating-port. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
cd "$WORKDIR" || exit 0
export PYTHONDONTWRITEBYTECODE=1
lib_run 180 "$SCRATCH/py.out" python3 .verifier/pyrunner.py \
  tests.test_codecs tests.test_layouts_and_rating \
  tests.test_signed_fields tests.test_rating_rules tests.test_batch_control tests.test_golden_files
lib_parse_result_lines "$SCRATCH/py.out"
