SELECT meter_id, day, wh_total, actual_intervals, estimated_intervals, missing_intervals
FROM daily_usage WHERE meter_id = 'MTR-000401';
