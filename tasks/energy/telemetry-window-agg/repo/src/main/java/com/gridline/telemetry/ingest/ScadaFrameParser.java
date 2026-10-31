package com.gridline.telemetry.ingest;

import com.gridline.telemetry.model.Quality;
import com.gridline.telemetry.model.Reading;

/**
 * Parses frames from the SCADA front-end processor:
 * {@code SCADA|1|<feeder>|<epochMillis>|<valueKw>|<q>*<XX>} where {@code XX} is the hex XOR of all
 * characters between the leading {@code S} and the {@code *} (NMEA-style checksum).
 */
public class ScadaFrameParser {
    private static final String PREFIX = "SCADA|";

    public Reading parse(String frame) throws ParseException {
        if (frame == null || !frame.startsWith(PREFIX)) throw new ParseException("not a SCADA frame", String.valueOf(frame));
        int star = frame.lastIndexOf('*');
        if (star < 0 || star + 3 != frame.length()) throw new ParseException("missing checksum", frame);
        int expected;
        try {
            expected = Integer.parseInt(frame.substring(star + 1), 16);
        } catch (NumberFormatException e) {
            throw new ParseException("bad checksum digits", frame);
        }
        if (checksum(frame.substring(0, star)) != expected) throw new ParseException("checksum mismatch", frame);

        String[] f = frame.substring(0, star).split("\\|", -1);
        if (f.length != 6) throw new ParseException("expected 6 fields", frame);
        if (!"1".equals(f[1])) throw new ParseException("unsupported frame version " + f[1], frame);
        try {
            return new Reading(f[2], Long.parseLong(f[3]), Double.parseDouble(f[4]), Quality.fromCode(f[5]));
        } catch (IllegalArgumentException e) {
            throw new ParseException("bad field: " + e.getMessage(), frame);
        }
    }

    /** XOR of all characters after the first one. */
    public static int checksum(String body) {
        int c = 0;
        for (int i = 1; i < body.length(); i++) c ^= body.charAt(i);
        return c & 0xFF;
    }

    public static String frame(String feeder, long ts, double kw, String q) {
        String body = PREFIX + "1|" + feeder + "|" + ts + "|" + kw + "|" + q;
        return body + "*" + String.format("%02X", checksum(body));
    }
}
