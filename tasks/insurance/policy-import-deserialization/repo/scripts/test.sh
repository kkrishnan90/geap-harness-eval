#!/usr/bin/env bash
# Compile and run the unit tests (no Maven in this build container).
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=build
rm -rf "$OUT" && mkdir -p "$OUT/main" "$OUT/test"
javac -encoding UTF-8 -d "$OUT/main" $(find src/main/java -name '*.java')
javac -encoding UTF-8 -cp "$OUT/main" -d "$OUT/test" $(find src/test/java -name '*.java')
classes=$(cd src/test/java && find . -name '*Test.java' ! -path './testkit/*' | sed -e 's|^\./||' -e 's|\.java$||' -e 's|/|.|g' | sort)
java -cp "$OUT/main:$OUT/test" testkit.TestRunner $classes
