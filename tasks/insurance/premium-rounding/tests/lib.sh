# Shared verifier helpers. Sourced by tests/run.sh of every task.
# Canonical copy: tasks/_shared/lib.sh -- each task carries an identical copy at tests/lib.sh
# so that a task package stays self-contained.
#
# Contract (docs/CONTRACTS.md §1): run.sh <workdir> <results_json>; always writes the JSON.
# Test outcomes are collected as lines "PASS <id>" / "FAIL <id>" in $RAW. A test listed in
# tests/expected_f2p.txt or tests/expected_p2p.txt counts as passed only if it reported PASS
# and never reported FAIL. Anything that did not run (compile error, crash, timeout) is failed.

LIB_TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

lib_init() {
  RESULTS_JSON="${2:-results.json}"
  case "$RESULTS_JSON" in /*) ;; *) RESULTS_JSON="$PWD/$RESULTS_JSON" ;; esac
  SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/verify.XXXXXX")"
  RAW="$SCRATCH/raw.txt"; LOG="$SCRATCH/log.txt"
  : > "$RAW"; : > "$LOG"
  trap lib_finish EXIT
  if [ -z "${1:-}" ] || ! WORKDIR="$(cd "$1" 2>/dev/null && pwd)"; then
    echo "verifier: workdir '${1:-}' not found" >> "$LOG"
    exit 0
  fi
  export LC_ALL=C
}

# Copy hidden test files (tests/overlay/**) into the workdir, replacing agent copies.
lib_overlay() {
  if [ -d "$LIB_TESTS_DIR/overlay" ]; then
    cp -R "$LIB_TESTS_DIR/overlay/." "$WORKDIR/" >> "$LOG" 2>&1
  fi
}

# lib_run <timeout_s> <outfile> <cmd...>
# Runs cmd (in the current dir) with a watchdog; stdout+stderr go to outfile and the log.
lib_run() {
  local t="$1" out="$2"; shift 2
  echo "\$ $*" >> "$LOG"
  "$@" > "$out" 2>&1 < /dev/null &
  local pid=$!
  (
    i=0
    while [ "$i" -lt $((t * 10)) ]; do
      sleep 0.1
      kill -0 "$pid" 2>/dev/null || exit 0
      i=$((i + 1))
    done
    pkill -9 -P "$pid" 2>/dev/null
    kill -9 "$pid" 2>/dev/null
    echo "verifier: TIMEOUT after ${t}s: $*" >> "$out"
  ) > /dev/null 2>&1 &
  local w=$!
  wait "$pid"; local rc=$?
  wait "$w" 2>/dev/null
  cat "$out" >> "$LOG"
  echo "[exit $rc]" >> "$LOG"
  return $rc
}

# Lines "RESULT PASS <id>" / "RESULT FAIL <id>" (main-based harnesses, pyrunner, node reporter).
lib_parse_result_lines() {
  sed -nE 's/^RESULT (PASS|FAIL) (.+)$/\1 \2/p' "$1" >> "$RAW"
}

# go test -v output: "--- PASS: TestX (0.00s)" (subtests are indented, ids like TestX/case).
lib_parse_go() {
  sed -nE 's/^[[:space:]]*--- (PASS|FAIL): ([^[:space:]]+).*/\1 \2/p' "$1" >> "$RAW"
}

# cargo test output: "test mod::name ... ok|FAILED". Optional prefix is prepended as "<prefix>::".
lib_parse_cargo() {
  local file="$1" prefix="${2:-}"
  [ -n "$prefix" ] && prefix="$prefix::"
  sed -nE 's/^test (.+) \.\.\. (ok|FAILED)$/\2 \1/p' "$file" \
    | sed -E -e 's/^ok /PASS /' -e 's/^FAILED /FAIL /' \
    | sed -E "s/^(PASS|FAIL) /\\1 $prefix/" >> "$RAW"
}

_lib_json_escape() {
  # keep printable ASCII + newline; escape backslash and quote; join lines with \n
  tr '\t\r' '  ' | tr -cd '\12\40-\176' | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' \
    | awk 'BEGIN{ORS=""} NR>1{print "\\n"} {print}'
}

_lib_group_json() {
  local list="$1" passed=0 total=0 failed="" name
  if [ -f "$list" ]; then
    while IFS= read -r name || [ -n "$name" ]; do
      case "$name" in ''|'#'*) continue ;; esac
      total=$((total + 1))
      if grep -qxF "PASS $name" "$RAW" && ! grep -qxF "FAIL $name" "$RAW"; then
        passed=$((passed + 1))
      else
        [ -n "$failed" ] && failed="$failed, "
        failed="$failed\"$(printf '%s' "$name" | _lib_json_escape)\""
      fi
    done < "$list"
  fi
  printf '{"passed": %d, "total": %d, "failed": [%s]}' "$passed" "$total" "$failed"
}

lib_finish() {
  local f2p p2p tail_txt tmp
  f2p="$(_lib_group_json "$LIB_TESTS_DIR/expected_f2p.txt")"
  p2p="$(_lib_group_json "$LIB_TESTS_DIR/expected_p2p.txt")"
  tail_txt="$(tail -c 4000 "$LOG" 2>/dev/null | _lib_json_escape)"
  tmp="$RESULTS_JSON.tmp.$$"
  mkdir -p "$(dirname "$RESULTS_JSON")" 2>/dev/null
  printf '{"fail_to_pass": %s,\n "pass_to_pass": %s,\n "log_tail": "%s"}\n' "$f2p" "$p2p" "$tail_txt" > "$tmp" \
    && mv -f "$tmp" "$RESULTS_JSON"
  rm -rf "$SCRATCH"
}

# lib_java <testkit_src_dir> <main_src_dir> <test_src_root> <fqcn>...
# Compiles main sources once, then compiles + runs each test class on its own, so a test
# class that does not compile (e.g. it uses API the seed lacks) only fails its own tests.
lib_java() {
  local testkit="$1" main="$2" troot="$3"; shift 3
  local B="$SCRATCH/jbuild" fq src out
  mkdir -p "$B/main" "$B/testkit"
  find "$main" -name '*.java' > "$B/main.list"
  if ! lib_run 180 "$SCRATCH/javac-main.out" javac -nowarn -encoding UTF-8 -d "$B/main" @"$B/main.list"; then
    echo "verifier: main sources failed to compile; all tests count as failed" >> "$LOG"
    return 1
  fi
  lib_run 60 "$SCRATCH/javac-testkit.out" javac -nowarn -encoding UTF-8 -d "$B/testkit" "$testkit"/*.java || return 1
  for fq in "$@"; do
    src="$troot/$(printf '%s' "$fq" | tr . /).java"
    out="$B/t-$fq"
    mkdir -p "$out"
    if lib_run 120 "$SCRATCH/javac-$fq.out" javac -nowarn -encoding UTF-8 -cp "$B/main:$B/testkit" -d "$out" "$src"; then
      lib_run "${JAVA_TEST_TIMEOUT:-300}" "$SCRATCH/java-$fq.out" java -cp "$B/main:$B/testkit:$out" testkit.TestRunner "$fq"
      lib_parse_result_lines "$SCRATCH/java-$fq.out"
    else
      echo "verifier: test class $fq failed to compile" >> "$LOG"
    fi
  done
}

# Environment for offline, reproducible go/cargo runs.
lib_offline_env() {
  export GOTOOLCHAIN=local GOPROXY=off GOFLAGS=-mod=mod GOSUMDB=off
  export CARGO_NET_OFFLINE=true CARGO_TERM_COLOR=never
  export NODE_NO_WARNINGS=1
}
