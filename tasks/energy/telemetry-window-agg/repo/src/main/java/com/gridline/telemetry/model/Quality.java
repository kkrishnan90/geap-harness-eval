package com.gridline.telemetry.model;

/** IEC 61850-style quality, collapsed to what the analytics layer needs. */
public enum Quality {
    GOOD,
    /** Value delivered but flagged (substituted, old data, inaccurate). Aggregated, but counted. */
    SUSPECT,
    /** Invalid / failed sensor. Never aggregated. */
    BAD;

    public static Quality fromCode(String code) {
        switch (code.trim().toUpperCase(java.util.Locale.ROOT)) {
            case "G": case "GOOD": return GOOD;
            case "S": case "SUSPECT": return SUSPECT;
            case "B": case "BAD": case "INVALID": return BAD;
            default: throw new IllegalArgumentException("unknown quality code: " + code);
        }
    }
}
