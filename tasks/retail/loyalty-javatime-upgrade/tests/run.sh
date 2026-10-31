#!/usr/bin/env bash
# Verifier for retail/loyalty-javatime-upgrade. Usage: run.sh <workdir> <results_json>
# The repo's legacy DateHandlingTest is the agent's to migrate and is not run here.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
cd "$WORKDIR" || exit 0
lib_java src/test/java/testkit src/main/java src/test/java \
  com.brightmart.loyalty.EarnAndTierTest \
  com.brightmart.loyalty.LoyaltyJavaTimeApiTest \
  com.brightmart.loyalty.PointsExpiryZoneTest \
  com.brightmart.loyalty.TierAnniversaryTest \
  com.brightmart.loyalty.StatementFormatterConcurrencyTest
