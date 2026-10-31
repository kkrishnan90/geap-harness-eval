#!/usr/bin/env bash
# Usage: bin/ingest.sh <db> <raw_readings.csv> <meter_assignments.csv>
# CSVs have a header row and the column order of the tables in sql/schema.sql.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
db="$1"; raw="$2"; assign="$3"
sqlite3 -bail "$db" < "$here/sql/schema.sql"
sqlite3 -bail "$db" <<SQL
.mode csv
.import --skip 1 $raw raw_readings
.import --skip 1 $assign meter_assignments
UPDATE raw_readings SET wh = NULL WHERE wh = '';
UPDATE meter_assignments SET valid_to = NULL WHERE valid_to = '';
SQL
sqlite3 -bail "$db" < "$here/sql/dedupe.sql"
sqlite3 -bail "$db" < "$here/sql/daily_rollup.sql"
echo "ingested: $(sqlite3 "$db" 'SELECT COUNT(*) FROM readings') readings, $(sqlite3 "$db" 'SELECT COUNT(*) FROM daily_usage') meter-days"
