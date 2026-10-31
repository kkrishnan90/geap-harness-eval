#!/usr/bin/env bash
# Verifier for insurance/policy-import-deserialization. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
cd "$WORKDIR" || exit 0
lib_java src/test/java/testkit src/main/java src/test/java \
  com.meridianre.policy.io.PolicyRoundTripTest \
  com.meridianre.policy.service.ImportServiceTest \
  com.meridianre.policy.rating.PremiumCalculatorTest \
  com.meridianre.policy.io.ImportCompatibilityTest \
  com.meridianre.policy.io.PolicyImportFilterTest \
  com.meridianre.policy.io.PolicyImportLimitsTest \
  com.meridianre.policy.service.ImportServiceSecurityTest
