#!/usr/bin/env bash
# Verifier for healthcare/phi-redaction. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
cd "$WORKDIR" || exit 0
export PYTHONDONTWRITEBYTECODE=1
lib_run 120 "$SCRATCH/py.out" python3 .verifier/pyrunner.py \
  tests.test_formats tests.test_redactor tests.test_pipeline tests.test_shipping tests.test_phi_structured tests.test_phi_audit
lib_parse_result_lines "$SCRATCH/py.out"
