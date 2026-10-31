#!/usr/bin/env bash
# Verifier for banking/pain001-batch-booking. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
cd "$WORKDIR" || exit 0
lib_java src/test/java/testkit src/main/java src/test/java \
  com.northbank.payments.pain.Pain001ParserTest \
  com.northbank.payments.pain.PaymentValidatorTest \
  com.northbank.payments.pain.DebitBookingPlannerTest \
  com.northbank.payments.calendar.TargetCalendarTest \
  com.northbank.payments.pain.BatchBookingRegressionTest \
  com.northbank.payments.pain.BatchBookingParserTest \
  com.northbank.payments.pain.BatchBookingValidationTest \
  com.northbank.payments.pain.BatchBookingPlannerTest
