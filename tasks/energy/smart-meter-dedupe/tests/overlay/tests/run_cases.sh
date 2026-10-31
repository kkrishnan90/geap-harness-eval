#!/usr/bin/env bash
# Fixture runner. Usage: bash tests/run_cases.sh <cases_dir> [label]
# Prints "RESULT PASS|FAIL <label>/<case>/<check>" for every check.
# Run from the repository root.
cases="${1:-tests/cases}"
label="${2:-$(basename "$cases")}"
root="$(pwd)"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/meter-cases.XXXXXX")"
status=0
for case_dir in "$cases"/*/; do
  case_name="$(basename "$case_dir")"
  db="$tmp/$case_name.sqlite"
  setup_ok=1
  for step in "$root/sql/schema.sql" "$case_dir/input.sql" "$root/sql/dedupe.sql" "$root/sql/daily_rollup.sql"; do
    if ! sqlite3 -bail "$db" < "$step" > "$tmp/setup.log" 2>&1; then
      echo "setup failed for $case_name at $(basename "$step"):"; cat "$tmp/setup.log"
      setup_ok=0
      break
    fi
  done
  for check in "$case_dir"/checks/*.sql; do
    name="$(basename "$check" .sql)"
    id="$label/$case_name/$name"
    : > "$tmp/diff.txt"
    if [ "$setup_ok" = 1 ] && (cd "$root" && sqlite3 -bail -csv -header "$db" < "$check") > "$tmp/out.raw" 2>&1 \
        && tr -d '\r' < "$tmp/out.raw" > "$tmp/out.csv" \
        && diff -u "${check%.sql}.csv" "$tmp/out.csv" > "$tmp/diff.txt"; then
      echo "RESULT PASS $id"
    else
      echo "RESULT FAIL $id"
      if [ -s "$tmp/diff.txt" ]; then head -20 "$tmp/diff.txt"; else head -5 "$tmp/out.raw" 2>/dev/null; fi
      status=1
    fi
  done
done
rm -rf "$tmp"
exit $status
