-- Feeder load per UTC day (network planning). Meters without a feeder are
-- reported under 'UNASSIGNED'.
SELECT COALESCE(feeder_id, 'UNASSIGNED') AS feeder_id,
       day,
       COUNT(*)                          AS meters,
       SUM(wh_total)                     AS wh_total,
       MAX(wh_total)                     AS max_meter_wh
FROM daily_usage
GROUP BY COALESCE(feeder_id, 'UNASSIGNED'), day
ORDER BY feeder_id, day;
