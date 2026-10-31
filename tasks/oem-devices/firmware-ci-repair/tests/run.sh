#!/usr/bin/env bash
# Verifier for oem-devices/firmware-ci-repair. Usage: run.sh <workdir> <results_json>
# Part 1 exercises the agent's build (make ci / make test) on fresh copies of the workdir
# with probe tests dropped in. Part 2 builds the unit tests directly with clang.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
lib_offline_env
TD="$LIB_TESTS_DIR"
unset MAKEFLAGS MFLAGS CFLAGS CPPFLAGS LDFLAGS CC

fresh_copy() {  # fresh_copy <dir>: copy of the workdir without build outputs
  rm -rf "$1"; mkdir -p "$1"
  cp -R "$WORKDIR/." "$1/"
  rm -rf "$1/build"
  find "$1" \( -name '*.o' -o -name '*.a' -o -name '*.d' \) -delete 2>/dev/null
}
mark() { echo "$1 $2" >> "$RAW"; }

# --- A: clean `make ci` with a probe test --------------------------------------------
A="$SCRATCH/ci-a"; fresh_copy "$A"
cp "$TD/probes/test_zz_ci_probe.c" "$A/tests/"
cd "$A" || exit 0
if lib_run 240 "$SCRATCH/a.out" make ci; then
  mark PASS ci.make_ci_succeeds
  if grep -q '^CI-PROBE-RAN BUILD_TAG=dev$' "$SCRATCH/a.out"; then
    mark PASS ci.tests_actually_run
  else
    mark FAIL ci.tests_actually_run
  fi
  # --- C: header change must be picked up by an incremental `make test` --------------
  sleep 1.2  # make 3.81 compares mtimes with 1s resolution
  sed -i.bak 's/#define BOOTCFG_BUILD_TAG "dev"/#define BOOTCFG_BUILD_TAG "probe-7731"/' include/bootcfg_build.h && rm -f include/bootcfg_build.h.bak  # portable: GNU + BSD sed
  if lib_run 240 "$SCRATCH/c.out" make test && grep -q '^CI-PROBE-RAN BUILD_TAG=probe-7731$' "$SCRATCH/c.out"; then
    mark PASS ci.header_change_rebuilds
  else
    mark FAIL ci.header_change_rebuilds
  fi
else
  mark FAIL ci.make_ci_succeeds
fi

# --- B: a failing test must fail `make ci` ---------------------------------------------
if grep -qx 'PASS ci.make_ci_succeeds' "$RAW"; then
  B="$SCRATCH/ci-b"; fresh_copy "$B"
  cp "$TD/probes/test_zz_fail_probe.c" "$B/tests/"
  cd "$B" || exit 0
  if ! lib_run 240 "$SCRATCH/b.out" make ci && grep -q '^CI-FAIL-PROBE-RAN$' "$SCRATCH/b.out"; then
    mark PASS ci.failing_test_fails_build
  fi
fi

# --- D: warnings policy kept (dry run of a full build) ---------------------------------
D="$SCRATCH/ci-d"; fresh_copy "$D"
cd "$D" || exit 0
lib_run 60 "$SCRATCH/d.out" make -n -B all
compile_lines="$(grep -E '(^|[[:space:]])-c([[:space:]]|$)' "$SCRATCH/d.out")"
if [ -n "$compile_lines" ] \
   && ! printf '%s\n' "$compile_lines" | grep -v -- '-Wall' | grep -q . \
   && ! printf '%s\n' "$compile_lines" | grep -v -- '-Wextra' | grep -q . \
   && ! printf '%s\n' "$compile_lines" | grep -v -- '-Werror' | grep -q . \
   && ! printf '%s\n' "$compile_lines" | grep -qE -- '-Wno-|-w([[:space:]]|$)|-Wno-error' \
   && ! grep -rqE '#[[:space:]]*pragma[[:space:]]+(clang|GCC)[[:space:]]+diagnostic' src include; then
  mark PASS ci.warning_flags_kept
else
  echo "verifier: compile lines missing -Wall/-Wextra/-Werror or warnings silenced" >> "$LOG"
  mark FAIL ci.warning_flags_kept
fi

# --- E: unit tests, built directly ------------------------------------------------------
cd "$WORKDIR" || exit 0
for t in test_tlv test_fwver test_crc32 test_tlv_bounds; do
  if lib_run 120 "$SCRATCH/cc-$t.out" clang -std=c11 -Wall -O1 -Iinclude -Itests \
       -o "$SCRATCH/$t" "tests/$t.c" src/*.c; then
    lib_run 60 "$SCRATCH/$t.out" "$SCRATCH/$t"
    lib_parse_result_lines "$SCRATCH/$t.out"
  else
    echo "verifier: $t failed to compile" >> "$LOG"
  fi
done
