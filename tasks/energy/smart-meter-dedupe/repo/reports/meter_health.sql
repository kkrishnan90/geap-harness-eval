-- Meters whose read rate over the loaded period is below 90 % (field ops).
SELECT meter_id,
       COUNT(*)                                                         AS days,
       SUM(missing_intervals)                                           AS missing,
       ROUND(100.0 * SUM(96 - missing_intervals) / (96 * COUNT(*)), 1)  AS read_rate_pct
FROM daily_usage
GROUP BY meter_id
HAVING read_rate_pct < 90.0
ORDER BY read_rate_pct, meter_id;
