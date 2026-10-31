package com.gridline.telemetry.units;

import java.util.Locale;

/** Converts power values reported by heterogeneous RTUs to kW. */
public final class UnitConverter {
    private UnitConverter() {}

    public static double toKw(double value, String unit) {
        switch (unit.trim().toLowerCase(Locale.ROOT)) {
            case "w": return value / 1_000.0;
            case "kw": return value;
            case "mw": return value * 1_000.0;
            case "gw": return value * 1_000_000.0;
            default: throw new IllegalArgumentException("unsupported power unit: " + unit);
        }
    }
}
