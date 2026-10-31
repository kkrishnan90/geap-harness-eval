#!/usr/bin/env bash
# Verifier for healthcare/hl7-escape-handling. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
cd "$WORKDIR" || exit 0
export PYTHONDONTWRITEBYTECODE=1
lib_run 120 "$SCRATCH/py.out" python3 .verifier/pyrunner.py \
  tests.test_message tests.test_encoding_basic tests.test_support tests.test_escape_sequences
lib_parse_result_lines "$SCRATCH/py.out"
