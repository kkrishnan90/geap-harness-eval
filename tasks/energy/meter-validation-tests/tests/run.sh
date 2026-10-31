#!/usr/bin/env bash
# Verifier for energy/meter-validation-tests (test-authoring).
# Usage: run.sh <workdir> <results_json>
#  1. pristine implementation + visible tests are overlaid; go test ./... gives P2P
#  2. the agent's internal/vee/rules_test.go must define >= MIN_TESTS tests that all pass on the reference
#  3. each hidden mutant of internal/vee must make at least one of those tests fail ("killed")
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_offline_env
MIN_TESTS=8
AGENT_FILE=internal/vee/rules_test.go
cd "$WORKDIR" || exit 0
# agent tests elsewhere in the package must not interfere with the reference check
lib_overlay

[ -f "$AGENT_FILE" ] && cp "$AGENT_FILE" "$SCRATCH/agent_rules_test.go"
rm -f "$AGENT_FILE"
lib_run 300 "$SCRATCH/p2p.out" go test -count=1 -vet=off -v ./...
lib_parse_go "$SCRATCH/p2p.out"

[ -f "$SCRATCH/agent_rules_test.go" ] || { echo "verifier: $AGENT_FILE not found" >> "$LOG"; exit 0; }
cp "$SCRATCH/agent_rules_test.go" "$AGENT_FILE"
names="$(sed -nE 's/^func (Test[A-Za-z0-9_]+)\([A-Za-z_][A-Za-z0-9_]* \*testing\.T\).*/\1/p' "$AGENT_FILE" | sort -u)"
n=$(printf '%s\n' "$names" | grep -c . )
if [ "$n" -lt "$MIN_TESTS" ]; then
  echo "verifier: $AGENT_FILE defines $n tests, need >= $MIN_TESTS" >> "$LOG"; exit 0
fi
run_re="^($(printf '%s\n' "$names" | paste -sd '|' -))\$"

if lib_run 180 "$SCRATCH/ref.out" go test -count=1 -vet=off -v -run "$run_re" ./internal/vee/; then
  ok=1
  for t in $names; do grep -qE "^--- PASS: $t " "$SCRATCH/ref.out" || ok=0; done
  if [ "$ok" = 1 ]; then echo "PASS agent_tests_pass_on_reference" >> "$RAW"; else exit 0; fi
else
  echo "verifier: agent tests fail (or do not compile) on the reference implementation" >> "$LOG"; exit 0
fi

mkdir -p "$SCRATCH/ref_vee" && cp internal/vee/*.go "$SCRATCH/ref_vee/"
for m in "$LIB_TESTS_DIR"/mutants/*/; do
  name="$(basename "$m")"
  cp "$m"/*.go internal/vee/
  if lib_run 180 "$SCRATCH/m-$name.out" go test -count=1 -vet=off -v -run "$run_re" ./internal/vee/; then
    echo "verifier: mutant $name SURVIVED" >> "$LOG"
  else
    echo "PASS mutant::$name" >> "$RAW"; echo "verifier: mutant $name killed" >> "$LOG"
  fi
  cp "$SCRATCH/ref_vee/"*.go internal/vee/
done
