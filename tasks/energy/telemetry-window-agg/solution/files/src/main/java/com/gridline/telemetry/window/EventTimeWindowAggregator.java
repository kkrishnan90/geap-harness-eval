package com.gridline.telemetry.window;

import com.gridline.telemetry.model.Reading;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.TreeMap;

/**
 * Per-feeder tumbling / sliding window aggregation on event time with a watermark.
 *
 * <p>watermark = max event time seen - allowed lateness. A window {@code [start, end)} is emitted
 * (and its state dropped) as soon as {@code end <= watermark}. A reading whose windows are all
 * closed is late: it goes to the late sink and changes nothing. Not thread-safe (single consumer).
 */
public class EventTimeWindowAggregator implements WindowAggregator {
    private final WindowSpec spec;
    private final long allowedLatenessMillis;
    private final WindowSink sink;
    private final LateEventSink lateSink;

    /** windowEnd -> feederId -> accumulator; both levels sorted, which gives the emission order. */
    private final TreeMap<Long, TreeMap<String, Accumulator>> open = new TreeMap<>();
    private long maxEventTime = Long.MIN_VALUE;
    private long watermark = Long.MIN_VALUE;
    private long lateEvents;

    public EventTimeWindowAggregator(WindowSpec spec, long allowedLatenessMillis, WindowSink sink, LateEventSink lateSink) {
        this.spec = Objects.requireNonNull(spec, "spec");
        if (allowedLatenessMillis < 0) throw new IllegalArgumentException("allowed lateness must be >= 0");
        this.allowedLatenessMillis = allowedLatenessMillis;
        this.sink = Objects.requireNonNull(sink, "sink");
        this.lateSink = Objects.requireNonNull(lateSink, "lateSink");
    }

    @Override
    public void accept(Reading r) {
        long ts = r.timestampMillis();
        if (ts > maxEventTime) {
            maxEventTime = ts;
            watermark = ts - allowedLatenessMillis;
        }
        boolean assigned = false;
        for (long start = spec.lastStartFor(ts); start > ts - spec.sizeMillis(); start -= spec.slideMillis()) {
            long end = start + spec.sizeMillis();
            if (end <= watermark) continue;
            open.computeIfAbsent(end, k -> new TreeMap<>())
                .computeIfAbsent(r.feederId(), k -> new Accumulator())
                .add(r.valueKw());
            assigned = true;
        }
        if (!assigned) {
            lateEvents++;
            lateSink.onLate(r);
        }
        emitUpTo(watermark);
    }

    private void emitUpTo(long limit) {
        while (!open.isEmpty() && open.firstKey() <= limit) {
            Map.Entry<Long, TreeMap<String, Accumulator>> e = open.pollFirstEntry();
            emitAll(e.getKey(), e.getValue());
        }
    }

    private void emitAll(long end, TreeMap<String, Accumulator> byFeeder) {
        long start = end - spec.sizeMillis();
        for (Map.Entry<String, Accumulator> f : byFeeder.entrySet()) {
            sink.emit(f.getValue().toResult(f.getKey(), start, end));
        }
    }

    @Override
    public void flush() {
        emitUpTo(Long.MAX_VALUE);
    }

    public long watermark() {
        return watermark;
    }

    public long lateEventCount() {
        return lateEvents;
    }

    /** Number of (feeder, window) aggregates currently held in memory. */
    public int openWindowCount() {
        int n = 0;
        for (TreeMap<String, Accumulator> m : open.values()) n += m.size();
        return n;
    }

    /** Debug helper: open window ends in ascending order. */
    List<Long> openWindowEnds() {
        return new ArrayList<>(open.keySet());
    }
}
