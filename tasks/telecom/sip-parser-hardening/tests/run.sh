#!/usr/bin/env bash
# Verifier for telecom/sip-parser-hardening. Usage: run.sh <workdir> <results_json>
# The lib unit tests and every integration test target run separately, so a target that
# fails to compile (or aborts) only fails its own tests.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
lib_offline_env
cd "$WORKDIR" || exit 0
export CARGO_TARGET_DIR="$SCRATCH/target"
lib_run 300 "$SCRATCH/lib.out" cargo test --offline --lib
lib_parse_cargo "$SCRATCH/lib.out" lib
for t in parse_valid dialog_tx hardening_guards hardening_errors no_panic_fuzz; do
  lib_run 300 "$SCRATCH/$t.out" cargo test --offline --test "$t"
  lib_parse_cargo "$SCRATCH/$t.out" "$t"
done
