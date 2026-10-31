#!/usr/bin/env bash
# Verifier for banking/ledger-fx-rounding. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
cd "$WORKDIR" || exit 0
lib_java src/test/java/testkit src/main/java src/test/java \
  com.meridian.ledger.MoneyTest \
  com.meridian.ledger.FxTest \
  com.meridian.ledger.LedgerTest \
  com.meridian.ledger.RevaluationTest \
  com.meridian.ledger.ReportingTest \
  com.meridian.ledger.RoundingPolicyTest \
  com.meridian.ledger.FxPrecisionTest \
  com.meridian.ledger.LedgerInvariantTest \
  com.meridian.ledger.RevaluationScenarioTest \
  com.meridian.ledger.RevaluationInvariantTest
