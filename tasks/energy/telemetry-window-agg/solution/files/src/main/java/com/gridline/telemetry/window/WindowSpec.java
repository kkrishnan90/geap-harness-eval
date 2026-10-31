package com.gridline.telemetry.window;

/**
 * Event-time window definition. Windows are aligned to the epoch: they start at multiples of
 * {@link #slideMillis()} and are {@link #sizeMillis()} long. Tumbling windows have slide == size.
 */
public final class WindowSpec {
    private final long sizeMillis;
    private final long slideMillis;

    private WindowSpec(long sizeMillis, long slideMillis) {
        if (sizeMillis <= 0) throw new IllegalArgumentException("window size must be positive");
        if (slideMillis <= 0) throw new IllegalArgumentException("slide must be positive");
        if (slideMillis > sizeMillis) throw new IllegalArgumentException("slide must not exceed size");
        if (sizeMillis % slideMillis != 0) throw new IllegalArgumentException("size must be a multiple of slide");
        this.sizeMillis = sizeMillis;
        this.slideMillis = slideMillis;
    }

    public static WindowSpec tumbling(long sizeMillis) {
        return new WindowSpec(sizeMillis, sizeMillis);
    }

    public static WindowSpec sliding(long sizeMillis, long slideMillis) {
        return new WindowSpec(sizeMillis, slideMillis);
    }

    public long sizeMillis() { return sizeMillis; }

    public long slideMillis() { return slideMillis; }

    public boolean isTumbling() { return sizeMillis == slideMillis; }

    /** Start of the latest window containing {@code ts}. */
    long lastStartFor(long ts) {
        return Math.floorDiv(ts, slideMillis) * slideMillis;
    }

    @Override
    public String toString() {
        return isTumbling() ? "tumbling(" + sizeMillis + ")" : "sliding(" + sizeMillis + "," + slideMillis + ")";
    }
}
