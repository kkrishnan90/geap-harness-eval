#!/usr/bin/env bash
# Verifier for oem-devices/ota-manifest-verify. Usage: run.sh <workdir> <results_json>
# The lib unit tests and every integration test target are built and run separately, so a
# target that fails to compile only fails its own tests.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
lib_offline_env
cd "$WORKDIR" || exit 0
export CARGO_TARGET_DIR="$SCRATCH/target"
lib_run 300 "$SCRATCH/lib.out" cargo test --offline --lib
lib_parse_cargo "$SCRATCH/lib.out" lib
for t in sha256_vectors manifest_v1 manifest_v2 rollback_and_chunks; do
  lib_run 300 "$SCRATCH/$t.out" cargo test --offline --test "$t"
  lib_parse_cargo "$SCRATCH/$t.out" "$t"
done
