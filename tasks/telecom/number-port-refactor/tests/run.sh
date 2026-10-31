#!/usr/bin/env bash
# Verifier for telecom/number-port-refactor. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
lib_offline_env
cd "$WORKDIR" || exit 0
for f in calendar audit_operators handlers decision_table rules_module; do
  lib_run 120 "$SCRATCH/node-$f.out" node --test --test-reporter=./.verifier/reporter.mjs "test/$f.test.ts"
  lib_parse_result_lines "$SCRATCH/node-$f.out"
done
