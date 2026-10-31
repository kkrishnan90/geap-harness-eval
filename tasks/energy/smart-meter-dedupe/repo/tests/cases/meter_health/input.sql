INSERT INTO meter_assignments VALUES ('MTR-000401', 'FDR-40', '2025-01-01', NULL),
                                     ('MTR-000402', 'FDR-40', '2025-01-01', NULL);
WITH RECURSIVE n(i) AS (SELECT 0 UNION ALL SELECT i + 1 FROM n WHERE i < 95)
INSERT INTO raw_readings
SELECT 'MTR-000401', strftime('%Y-%m-%dT%H:%M:%SZ', '2026-03-03', '+' || (i * 15) || ' minutes'),
       100 + i, CASE WHEN i % 10 = 0 THEN 'E' ELSE 'A' END, '2026-03-04T02:00:00Z', 'B3'
FROM n;
WITH RECURSIVE n(i) AS (SELECT 0 UNION ALL SELECT i + 1 FROM n WHERE i < 59)
INSERT INTO raw_readings
SELECT 'MTR-000402', strftime('%Y-%m-%dT%H:%M:%SZ', '2026-03-03', '+' || (i * 15) || ' minutes'),
       50, CASE WHEN i % 2 = 0 THEN 'E' ELSE 'A' END, '2026-03-04T02:00:00Z', 'B3'
FROM n;
