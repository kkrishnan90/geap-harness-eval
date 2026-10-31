#!/usr/bin/env bash
# Verifier for logistics/route-batch-csv-ingest (ci-repair).
# Usage: run.sh <workdir> <results_json>
#  1. run the agent's own CI entrypoint (scripts/ci.sh) from a foreign cwd under two hash seeds;
#     it must exit 0, run the lint cleanly, and report every pre-existing test as "ok"
#  2. overlay hidden behavioural ingest tests and run them against src/
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
export PYTHONDONTWRITEBYTECODE=1

if [ -f "$WORKDIR/scripts/ci.sh" ]; then
  for seed in 1 3; do
    cd "$SCRATCH" || exit 0
    if PYTHONHASHSEED=$seed lib_run 180 "$SCRATCH/ci-$seed.out" bash "$WORKDIR/scripts/ci.sh"; then
      echo "PASS ci::exit_zero_hashseed_$seed" >> "$RAW"
    fi
  done
  out="$SCRATCH/ci-1.out"
  grep -q '^lint: 0 finding(s)$' "$out" && echo "PASS ci::lint_ran_clean" >> "$RAW"
  while IFS= read -r t || [ -n "$t" ]; do
    [ -z "$t" ] && continue
    method="${t#*.}"
    pat="^$method \\(([A-Za-z0-9_]+\\.)*$t\\) \\.\\.\\. ok\$"
    if grep -Eq "$pat" "$out"; then echo "PASS ci::$t" >> "$RAW"; fi
  done < "$LIB_TESTS_DIR/visible_tests.txt"
else
  echo "verifier: scripts/ci.sh missing" >> "$LOG"
fi

lib_overlay
cd "$WORKDIR" || exit 0
PYTHONPATH="src:.verifier/hidden" lib_run 120 "$SCRATCH/hidden.out" python3 .verifier/pyrunner.py test_ingest_hidden
lib_parse_result_lines "$SCRATCH/hidden.out"
