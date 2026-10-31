#!/usr/bin/env bash
# Compile and run all tests with the in-repo testkit (no Maven/Gradle in this environment).
#   scripts/test.sh                 # all *Test classes
#   scripts/test.sh InventoryRepositoryTest   # classes whose name matches
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=build
rm -rf "$OUT" && mkdir -p "$OUT/main" "$OUT/test"
javac -encoding UTF-8 -d "$OUT/main" $(find src/main/java -name '*.java')
javac -encoding UTF-8 -cp "$OUT/main" -d "$OUT/test" $(find src/test/java -name '*.java')
classes=$(cd src/test/java && find . -name '*Test.java' | sed -e 's|^\./||' -e 's|\.java$||' -e 's|/|.|g' | grep -E "${1:-.}" | sort)
java -cp "$OUT/main:$OUT/test" testkit.TestRunner $classes
