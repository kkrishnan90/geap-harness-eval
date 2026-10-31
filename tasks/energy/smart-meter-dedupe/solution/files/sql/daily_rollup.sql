-- Rebuild daily_usage from readings: one row per meter and UTC day that has
-- at least one reading. The feeder is the assignment valid on that day
-- (valid_from inclusive, valid_to exclusive, NULL = open); NULL if none.
DELETE FROM daily_usage;

INSERT INTO daily_usage (meter_id, day, feeder_id, wh_total, actual_intervals,
                         estimated_intervals, missing_intervals)
SELECT d.meter_id,
       d.day,
       (SELECT a.feeder_id
          FROM meter_assignments a
         WHERE a.meter_id = d.meter_id
           AND a.valid_from <= d.day
           AND (a.valid_to IS NULL OR d.day < a.valid_to)
         ORDER BY a.valid_from DESC
         LIMIT 1)                AS feeder_id,
       d.wh_total,
       d.actual_intervals,
       d.estimated_intervals,
       96 - d.n                  AS missing_intervals
FROM (
    SELECT meter_id,
           substr(interval_start, 1, 10)                     AS day,
           SUM(wh)                                           AS wh_total,
           SUM(CASE quality WHEN 'A' THEN 1 ELSE 0 END)      AS actual_intervals,
           SUM(CASE quality WHEN 'E' THEN 1 ELSE 0 END)      AS estimated_intervals,
           COUNT(*)                                          AS n
    FROM readings
    GROUP BY meter_id, substr(interval_start, 1, 10)
) d;
