#!/usr/bin/env bash
# Compile main + test sources and run every *Test class with the in-house runner.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=build
rm -rf "$OUT" && mkdir -p "$OUT/main" "$OUT/test"
javac -nowarn -encoding UTF-8 -d "$OUT/main" $(find src/main/java -name '*.java')
javac -nowarn -encoding UTF-8 -cp "$OUT/main" -d "$OUT/test" $(find src/test/java -name '*.java')
classes=$(cd src/test/java && find . -name '*Test.java' | sed -e 's|^\./||' -e 's|\.java$||' -e 's|/|.|g' | sort)
java -cp "$OUT/main:$OUT/test" testkit.TestRunner $classes
