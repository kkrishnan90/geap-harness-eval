-- Rebuild readings: exactly one row per (meter_id, interval_start).
-- HES resends intervals (retries, re-estimation, late actuals), so raw_readings
-- contains duplicates. Selection rule (ING-412):
--   1. rows with wh IS NULL ("no data") are ignored,
--   2. an actual read (A) always beats an estimate (E),
--   3. then the latest received_at wins,
--   4. then the row loaded last (highest rowid) wins.
DELETE FROM readings;

INSERT INTO readings (meter_id, interval_start, wh, quality, received_at)
SELECT meter_id, interval_start, wh, quality, received_at
FROM (
    SELECT meter_id, interval_start, wh, quality, received_at,
           ROW_NUMBER() OVER (
               PARTITION BY meter_id, interval_start
               ORDER BY CASE quality WHEN 'A' THEN 0 ELSE 1 END,
                        received_at DESC,
                        rowid DESC
           ) AS rn
    FROM raw_readings
    WHERE wh IS NOT NULL
)
WHERE rn = 1;
