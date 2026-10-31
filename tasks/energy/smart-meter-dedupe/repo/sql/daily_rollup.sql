-- Rebuild daily_usage from readings: one row per meter and UTC day that has
-- at least one reading.
DELETE FROM daily_usage;

INSERT INTO daily_usage (meter_id, day, feeder_id, wh_total, actual_intervals,
                         estimated_intervals, missing_intervals)
SELECT r.meter_id,
       substr(r.interval_start, 1, 10)                       AS day,
       a.feeder_id,
       SUM(r.wh)                                             AS wh_total,
       SUM(CASE r.quality WHEN 'A' THEN 1 END)               AS actual_intervals,
       SUM(CASE r.quality WHEN 'E' THEN 1 END)               AS estimated_intervals,
       96 - COUNT(*)                                         AS missing_intervals
FROM readings r
LEFT JOIN meter_assignments a ON a.meter_id = r.meter_id
GROUP BY r.meter_id, substr(r.interval_start, 1, 10), a.feeder_id;
