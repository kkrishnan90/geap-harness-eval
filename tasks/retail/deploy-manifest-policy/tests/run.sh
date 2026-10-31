#!/usr/bin/env bash
# Verifier for retail/deploy-manifest-policy. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
cd "$WORKDIR" || exit 0
export PYTHONDONTWRITEBYTECODE=1
lib_run 180 "$SCRATCH/py.out" python3 .verifier/pyrunner.py \
  tests.test_quantity tests.test_rules \
  hidden_tests.test_quantity_binary hidden_tests.test_policy_guard hidden_tests.test_manifests
lib_parse_result_lines "$SCRATCH/py.out"
