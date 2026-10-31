SELECT day, actual_intervals, estimated_intervals, typeof(actual_intervals) AS ta,
       typeof(estimated_intervals) AS te FROM daily_usage ORDER BY day;
