#!/usr/bin/env bash
# Verifier for retail/cart-stackable-promos. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
lib_offline_env
cd "$WORKDIR" || exit 0
for f in money tax_shipping engine stacking; do
  lib_run 120 "$SCRATCH/node-$f.out" node --test --test-reporter=./.verifier/reporter.mjs "test/$f.test.ts"
  lib_parse_result_lines "$SCRATCH/node-$f.out"
done
