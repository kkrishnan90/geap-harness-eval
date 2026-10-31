#!/usr/bin/env bash
# Verifier for energy/smart-meter-dedupe. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
cd "$WORKDIR" || exit 0
lib_run 120 "$SCRATCH/cases.out" bash tests/run_cases.sh tests/cases cases
lib_parse_result_lines "$SCRATCH/cases.out"
lib_run 120 "$SCRATCH/hidden.out" bash tests/run_cases.sh tests/hidden_cases hidden
lib_parse_result_lines "$SCRATCH/hidden.out"
rm -rf "$WORKDIR/tests/hidden_cases"
