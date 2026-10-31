package com.gridline.telemetry.window;

/**
 * Aggregate of the readings of one feeder within {@code [windowStart, windowEnd)} (event time,
 * epoch millis).
 */
public record WindowResult(String feederId, long windowStart, long windowEnd, long count,
                           double sumKw, double minKw, double maxKw) {
    public double avgKw() {
        return count == 0 ? 0.0 : sumKw / count;
    }

    /** Energy in kWh assuming the average power held for the whole window. */
    public double energyKwh() {
        return avgKw() * (windowEnd - windowStart) / 3_600_000.0;
    }
}
