#!/usr/bin/env bash
# Verifier for telecom/e164-normalizer. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
lib_offline_env
cd "$WORKDIR" || exit 0
# One node process per file so a module that fails to load only fails its own file's tests.
for f in e164 msisdn porting e164_dialling; do
  lib_run 120 "$SCRATCH/node-$f.out" node --test --test-reporter=./.verifier/reporter.mjs "test/$f.test.ts"
  lib_parse_result_lines "$SCRATCH/node-$f.out"
done
