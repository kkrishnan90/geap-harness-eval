#!/usr/bin/env bash
# Verifier for oem-devices/ble-gatt-state-machine. Usage: run.sh <workdir> <results_json>
# Each test file is compiled into its own binary (against all src/*.c) so one compile
# failure only fails that file's tests. Two structural checks verify the refactor itself.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
lib_offline_env
cd "$WORKDIR" || exit 0
for t in test_conn_mgr test_support test_golden_traces test_gfsm_api; do
  if lib_run 120 "$SCRATCH/cc-$t.out" clang -std=c11 -Wall -Wextra -O1 -Iinclude -Itests \
       -o "$SCRATCH/$t" "tests/$t.c" src/*.c; then
    lib_run 60 "$SCRATCH/$t.out" "$SCRATCH/$t"
    lib_parse_result_lines "$SCRATCH/$t.out"
  else
    echo "verifier: $t failed to compile" >> "$LOG"
  fi
done

# Refactor structure: no state dispatch by switch/case anywhere in src/, and the facade
# (conn_mgr.c) no longer talks to the HAL directly.
if grep -nE 'case[[:space:]]+CM_ST_' src/*.c >> "$LOG" 2>&1; then
  echo "FAIL structure.no_state_switch" >> "$RAW"
else
  echo "PASS structure.no_state_switch" >> "$RAW"
fi
if [ -f src/conn_mgr.c ] && ! grep -nE '\bhal_[a-z_]+[[:space:]]*\(' src/conn_mgr.c >> "$LOG" 2>&1; then
  echo "PASS structure.conn_mgr_is_facade" >> "$RAW"
else
  echo "FAIL structure.conn_mgr_is_facade" >> "$RAW"
fi
