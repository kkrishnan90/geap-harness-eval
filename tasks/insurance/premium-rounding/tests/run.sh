#!/usr/bin/env bash
# Verifier for insurance/premium-rounding. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
cd "$WORKDIR" || exit 0
lib_java src/test/java/testkit src/main/java src/test/java \
  com.harborline.motor.PremiumCalculatorTest \
  com.harborline.motor.PolicyAndClaimsTest \
  com.harborline.motor.PremiumRegressionGuardTest \
  com.harborline.motor.PremiumRoundingPolicyTest
