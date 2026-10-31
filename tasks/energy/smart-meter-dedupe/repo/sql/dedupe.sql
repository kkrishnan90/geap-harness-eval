-- Rebuild readings: exactly one row per (meter_id, interval_start).
-- HES resends intervals (retries, re-estimation, late actuals), so raw_readings
-- contains duplicates.
DELETE FROM readings;

INSERT INTO readings (meter_id, interval_start, wh, quality, received_at)
SELECT meter_id, interval_start, wh, quality, MIN(received_at)
FROM raw_readings
GROUP BY meter_id, interval_start;
