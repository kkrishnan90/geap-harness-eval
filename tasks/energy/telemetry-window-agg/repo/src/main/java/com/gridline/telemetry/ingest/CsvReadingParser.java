package com.gridline.telemetry.ingest;

import com.gridline.telemetry.model.Quality;
import com.gridline.telemetry.model.Reading;
import com.gridline.telemetry.units.UnitConverter;
import java.time.Instant;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.List;

/**
 * Parses the historian CSV export: {@code feeder_id,timestamp,value,unit,quality}.
 * Timestamps are ISO-8601 instants ({@code 2026-03-01T10:15:00Z}). A header line and blank lines
 * are skipped; lines starting with {@code #} are comments.
 */
public class CsvReadingParser {

    public Reading parseLine(String line) throws ParseException {
        String[] f = line.split(",", -1);
        if (f.length != 5) throw new ParseException("expected 5 fields", line);
        String feeder = f[0].trim();
        if (feeder.isEmpty()) throw new ParseException("empty feeder id", line);
        long ts;
        try {
            ts = Instant.parse(f[1].trim()).toEpochMilli();
        } catch (DateTimeParseException e) {
            throw new ParseException("bad timestamp", line);
        }
        double kw;
        try {
            kw = UnitConverter.toKw(Double.parseDouble(f[2].trim()), f[3]);
        } catch (IllegalArgumentException e) {
            throw new ParseException("bad value/unit", line);
        }
        Quality q;
        try {
            q = Quality.fromCode(f[4]);
        } catch (IllegalArgumentException e) {
            throw new ParseException("bad quality", line);
        }
        return new Reading(feeder, ts, kw, q);
    }

    /** Parses a whole export. Unparseable lines are collected into {@code rejects}. */
    public List<Reading> parseAll(List<String> lines, List<ParseException> rejects) {
        List<Reading> out = new ArrayList<>();
        for (String raw : lines) {
            String line = raw.strip();
            if (line.isEmpty() || line.startsWith("#") || line.startsWith("feeder_id,")) continue;
            try {
                out.add(parseLine(line));
            } catch (ParseException e) {
                rejects.add(e);
            }
        }
        return out;
    }
}
