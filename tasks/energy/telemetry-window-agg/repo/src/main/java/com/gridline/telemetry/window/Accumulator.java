package com.gridline.telemetry.window;

/** Mutable count/sum/min/max accumulator. Not thread-safe. */
public final class Accumulator {
    private long count;
    private double sum;
    private double min = Double.POSITIVE_INFINITY;
    private double max = Double.NEGATIVE_INFINITY;

    public void add(double v) {
        count++;
        sum += v;
        if (v < min) min = v;
        if (v > max) max = v;
    }

    public long count() { return count; }

    public boolean isEmpty() { return count == 0; }

    public WindowResult toResult(String feederId, long start, long end) {
        return new WindowResult(feederId, start, end, count, sum, min, max);
    }
}
