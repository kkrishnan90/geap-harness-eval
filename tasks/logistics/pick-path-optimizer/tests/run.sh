#!/usr/bin/env bash
# Verifier for logistics/pick-path-optimizer. Usage: run.sh <workdir> <results_json>
# The canonical src/oracle.rs and src/layout.rs are overlaid (lookup counting must not be
# altered). Every integration test target is built and run separately.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
lib_offline_env
cd "$WORKDIR" || exit 0
export CARGO_TARGET_DIR="$SCRATCH/target"
for t in route_basic batch_basic layout_slotting reference_equivalence lookup_budget; do
  lib_run 400 "$SCRATCH/$t.out" cargo test --offline --test "$t" -- --test-threads=4
  lib_parse_cargo "$SCRATCH/$t.out" "$t"
done
