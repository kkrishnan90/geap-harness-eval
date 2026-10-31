#!/usr/bin/env bash
# Verifier for oem-devices/spsc-ring-buffer-fix. Usage: run.sh <workdir> <results_json>
# Each test file is compiled into its own binary (against all src/*.c) so one compile
# failure only fails that file's tests. The agent's Makefile is not used.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
lib_offline_env
cd "$WORKDIR" || exit 0
for t in test_ring_basic test_lowpass test_imu_frame test_ring_wrap test_ring_threads; do
  if lib_run 120 "$SCRATCH/cc-$t.out" clang -std=c11 -Wall -O2 -Iinclude -Itests \
       -o "$SCRATCH/$t" "tests/$t.c" src/*.c -lpthread; then
    lib_run 120 "$SCRATCH/$t.out" "$SCRATCH/$t"
    lib_parse_result_lines "$SCRATCH/$t.out"
  else
    echo "verifier: $t failed to compile" >> "$LOG"
  fi
done
