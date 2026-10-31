#!/usr/bin/env bash
# Verifier for oem-devices/can-signed-signal. Usage: run.sh <workdir> <results_json>
# Each test file is compiled into its own binary (against all src/*.c) so one compile
# failure only fails that file's tests. The agent's Makefile is not used.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
lib_offline_env
cd "$WORKDIR" || exit 0
for t in test_candec test_dbc test_e2e test_signed_motorola; do
  if lib_run 120 "$SCRATCH/cc-$t.out" clang -std=c11 -Wall -O1 -Iinclude -Itests \
       -o "$SCRATCH/$t" "tests/$t.c" src/*.c -lm; then
    lib_run 60 "$SCRATCH/$t.out" "$SCRATCH/$t"
    lib_parse_result_lines "$SCRATCH/$t.out"
  else
    echo "verifier: $t failed to compile" >> "$LOG"
  fi
done
