SELECT meter_id, day, COALESCE(feeder_id, '<null>') AS feeder_id, wh_total, missing_intervals FROM daily_usage;
