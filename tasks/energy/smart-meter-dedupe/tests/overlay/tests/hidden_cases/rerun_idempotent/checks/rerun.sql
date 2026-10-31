.read sql/dedupe.sql
.read sql/daily_rollup.sql
SELECT meter_id, day, wh_total, actual_intervals FROM daily_usage;
SELECT COUNT(*) AS readings FROM readings;
