#!/usr/bin/env bash
# Verifier for insurance/claims-fraud-rules-tests (test-authoring).
# Usage: run.sh <workdir> <results_json>
#
# 1. Overlay pristine engine sources, testkit and P2P tests; run the P2P classes.
# 2. Compile + run the agent's FraudRulesEngineTest against the reference engine:
#    F2P "agent_tests_pass_on_reference" needs >= MIN_TESTS tests, all passing.
# 3. For each mutant engine in tests/mutants/<name>/, run the same compiled agent
#    tests against the mutant: F2P "mutant::<name>" passes when the suite fails
#    (only counted if step 2 passed).
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
cd "$WORKDIR" || exit 0

MIN_TESTS=8
AGENT_CLASS=com.harborline.claims.fraud.FraudRulesEngineTest
AGENT_SRC=src/test/java/com/harborline/claims/fraud/FraudRulesEngineTest.java

lib_java src/test/java/testkit src/main/java src/test/java \
  com.harborline.claims.fraud.FraudRulesEngineSmokeTest \
  com.harborline.claims.IntakeAndReserveTest \
  com.harborline.claims.fraud.FraudEngineBehaviourTest

JB="$SCRATCH/jbuild"
AGENT_OUT="$SCRATCH/agent-classes"
mkdir -p "$AGENT_OUT"
ref_ok=0
if [ ! -f "$AGENT_SRC" ]; then
  echo "verifier: $AGENT_SRC not found" >> "$LOG"
elif [ ! -d "$JB/main" ] || [ ! -d "$JB/testkit" ]; then
  echo "verifier: reference build missing" >> "$LOG"
elif lib_run 120 "$SCRATCH/javac-agent.out" javac -nowarn -encoding UTF-8 -cp "$JB/main:$JB/testkit" \
      -d "$AGENT_OUT" "$AGENT_SRC"; then
  lib_run 120 "$SCRATCH/agent-ref.out" java -cp "$JB/main:$JB/testkit:$AGENT_OUT" testkit.TestRunner "$AGENT_CLASS"
  rc=$?
  n_pass=$(grep -c '^RESULT PASS ' "$SCRATCH/agent-ref.out")
  n_fail=$(grep -c '^RESULT FAIL ' "$SCRATCH/agent-ref.out")
  echo "verifier: agent suite on reference: exit=$rc pass=$n_pass fail=$n_fail (need >= $MIN_TESTS, 0 failures)" >> "$LOG"
  if [ "$rc" -eq 0 ] && [ "$n_fail" -eq 0 ] && [ "$n_pass" -ge "$MIN_TESTS" ]; then
    ref_ok=1
  fi
else
  echo "verifier: agent test class failed to compile" >> "$LOG"
fi
if [ "$ref_ok" -eq 1 ]; then
  echo "PASS agent_tests_pass_on_reference" >> "$RAW"
else
  echo "FAIL agent_tests_pass_on_reference" >> "$RAW"
fi

for mdir in "$LIB_TESTS_DIR"/mutants/*/; do
  name="$(basename "$mdir")"
  if [ "$ref_ok" -ne 1 ]; then
    echo "FAIL mutant::$name" >> "$RAW"
    continue
  fi
  msrc="$SCRATCH/mut-$name/src"
  mout="$SCRATCH/mut-$name/classes"
  mkdir -p "$msrc" "$mout"
  cp -R "$LIB_TESTS_DIR/overlay/src/main/java/." "$msrc/"
  cp -R "$mdir/src/main/java/." "$msrc/"
  find "$msrc" -name '*.java' > "$SCRATCH/mut-$name/list"
  if ! lib_run 120 "$SCRATCH/javac-mut-$name.out" javac -nowarn -encoding UTF-8 -d "$mout" @"$SCRATCH/mut-$name/list"; then
    echo "verifier: mutant $name failed to compile (verifier bug)" >> "$LOG"
    echo "FAIL mutant::$name" >> "$RAW"
    continue
  fi
  lib_run 120 "$SCRATCH/agent-mut-$name.out" java -cp "$mout:$JB/testkit:$AGENT_OUT" testkit.TestRunner "$AGENT_CLASS"
  rc=$?
  m_fail=$(grep -c '^RESULT FAIL ' "$SCRATCH/agent-mut-$name.out")
  if [ "$rc" -ne 0 ] || [ "$m_fail" -gt 0 ]; then
    echo "verifier: mutant $name killed ($m_fail failing tests)" >> "$LOG"
    echo "PASS mutant::$name" >> "$RAW"
  else
    echo "verifier: mutant $name SURVIVED" >> "$LOG"
    echo "FAIL mutant::$name" >> "$RAW"
  fi
done
