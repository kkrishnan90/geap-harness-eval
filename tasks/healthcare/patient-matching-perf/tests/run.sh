#!/usr/bin/env bash
# Verifier for healthcare/patient-matching-perf. Usage: run.sh <workdir> <results_json>
# Overlays pristine scoring/normalize/synth modules (comparison counter is authoritative).
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
cd "$WORKDIR" || exit 0
export PYTHONDONTWRITEBYTECODE=1
lib_run 240 "$SCRATCH/py.out" python3 .verifier/pyrunner.py \
  tests.test_scoring tests.test_linker tests.test_io_report tests.test_linkage_budget
lib_parse_result_lines "$SCRATCH/py.out"
