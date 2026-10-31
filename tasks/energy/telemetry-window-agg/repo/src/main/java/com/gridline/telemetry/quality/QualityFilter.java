package com.gridline.telemetry.quality;

import com.gridline.telemetry.model.Quality;
import com.gridline.telemetry.model.Reading;
import java.util.EnumMap;
import java.util.Map;

/**
 * Drops readings that must not reach analytics: BAD quality, and values outside the feeder's
 * physical envelope (|kW| above {@code limitKw}, typically 1.5x the feeder rating).
 */
public class QualityFilter {
    public enum Reason { BAD_QUALITY, OUT_OF_RANGE }

    private final double limitKw;
    private final Map<Reason, Long> dropped = new EnumMap<>(Reason.class);
    private long suspectPassed;

    public QualityFilter(double limitKw) {
        if (limitKw <= 0) throw new IllegalArgumentException("limitKw must be positive");
        this.limitKw = limitKw;
    }

    /** @return true if the reading may be aggregated. */
    public synchronized boolean accept(Reading r) {
        if (r.quality() == Quality.BAD) return drop(Reason.BAD_QUALITY);
        if (Math.abs(r.valueKw()) > limitKw) return drop(Reason.OUT_OF_RANGE);
        if (r.quality() == Quality.SUSPECT) suspectPassed++;
        return true;
    }

    private boolean drop(Reason reason) {
        dropped.merge(reason, 1L, Long::sum);
        return false;
    }

    public synchronized long droppedCount(Reason reason) {
        return dropped.getOrDefault(reason, 0L);
    }

    public synchronized long suspectPassed() {
        return suspectPassed;
    }
}
