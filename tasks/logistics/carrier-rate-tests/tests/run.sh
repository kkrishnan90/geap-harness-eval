#!/usr/bin/env bash
# Verifier for logistics/carrier-rate-tests (test-authoring).
# Usage: run.sh <workdir> <results_json>
#  1. pristine implementation + visible tests are overlaid (P2P: existing + hidden reference tests)
#  2. the agent's tests/test_rates.py must pass on the reference implementation (>= MIN_TESTS tests)
#  3. each hidden mutant of parcelrate/rates.py must make the agent's tests fail ("killed")
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
MIN_TESTS=8
lib_overlay
cd "$WORKDIR" || exit 0
export PYTHONDONTWRITEBYTECODE=1
find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null

lib_run 120 "$SCRATCH/p2p.out" python3 .verifier/pyrunner.py \
  tests.test_zones tests.test_labels tests.test_tracking tests.test_rates_reference
lib_parse_result_lines "$SCRATCH/p2p.out"

[ -f tests/test_rates.py ] || { echo "verifier: tests/test_rates.py not found" >> "$LOG"; exit 0; }

count() { grep -c "^RESULT $1 " "$2" 2>/dev/null; }

lib_run 120 "$SCRATCH/ref.out" python3 .verifier/pyrunner.py tests.test_rates
ref_pass=$(count PASS "$SCRATCH/ref.out"); ref_fail=$(count FAIL "$SCRATCH/ref.out")
if [ "$ref_fail" -eq 0 ] && [ "$ref_pass" -ge "$MIN_TESTS" ] && ! grep -q '^IMPORT ERROR' "$SCRATCH/ref.out"; then
  echo "PASS agent_tests_pass_on_reference" >> "$RAW"
else
  echo "verifier: agent tests on reference: $ref_pass passed, $ref_fail failed (need >= $MIN_TESTS, 0 failed)" >> "$LOG"
  exit 0
fi

cp parcelrate/rates.py "$SCRATCH/rates.reference.py"
for m in "$LIB_TESTS_DIR"/mutants/*/; do
  name="$(basename "$m")"
  cp "$m/rates.py" parcelrate/rates.py
  lib_run 120 "$SCRATCH/m-$name.out" python3 .verifier/pyrunner.py tests.test_rates
  p=$(count PASS "$SCRATCH/m-$name.out"); f=$(count FAIL "$SCRATCH/m-$name.out")
  if [ "$f" -gt 0 ] || [ "$p" -lt "$ref_pass" ]; then
    echo "PASS mutant::$name" >> "$RAW"; echo "verifier: mutant $name killed" >> "$LOG"
  else
    echo "verifier: mutant $name SURVIVED" >> "$LOG"
  fi
  cp "$SCRATCH/rates.reference.py" parcelrate/rates.py
done
