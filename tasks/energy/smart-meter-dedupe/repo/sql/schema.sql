-- meter-ingest schema. Re-runnable: drops and recreates everything.
DROP TABLE IF EXISTS raw_readings;
DROP TABLE IF EXISTS readings;
DROP TABLE IF EXISTS daily_usage;
DROP TABLE IF EXISTS meter_assignments;

CREATE TABLE raw_readings (
    meter_id       TEXT NOT NULL,
    interval_start TEXT NOT NULL,          -- UTC, ISO-8601
    wh             INTEGER,                -- NULL when the HES reported "no data"
    quality        TEXT NOT NULL CHECK (quality IN ('A', 'E')),
    received_at    TEXT NOT NULL,          -- UTC, when the HES delivered the row
    batch_id       TEXT NOT NULL
);
CREATE INDEX raw_readings_key ON raw_readings (meter_id, interval_start);

CREATE TABLE readings (
    meter_id       TEXT NOT NULL,
    interval_start TEXT NOT NULL,
    wh             INTEGER NOT NULL,
    quality        TEXT NOT NULL,
    received_at    TEXT NOT NULL,
    PRIMARY KEY (meter_id, interval_start)
);

CREATE TABLE meter_assignments (
    meter_id   TEXT NOT NULL,
    feeder_id  TEXT NOT NULL,
    valid_from TEXT NOT NULL,              -- UTC date, inclusive
    valid_to   TEXT                        -- UTC date, exclusive; NULL = open
);

CREATE TABLE daily_usage (
    meter_id            TEXT NOT NULL,
    day                 TEXT NOT NULL,     -- UTC date
    feeder_id           TEXT,
    wh_total            INTEGER NOT NULL,
    actual_intervals    INTEGER,
    estimated_intervals INTEGER,
    missing_intervals   INTEGER NOT NULL,
    PRIMARY KEY (meter_id, day)
);
