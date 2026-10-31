#!/usr/bin/env bash
# Verifier for telecom/cdr-tiered-tariff. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
lib_offline_env
cd "$WORKDIR" || exit 0
lib_run 300 "$SCRATCH/go.out" go test -count=1 -vet=off -v ./...
lib_parse_go "$SCRATCH/go.out"
