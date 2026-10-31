package com.gridline.telemetry.window;

import com.gridline.telemetry.model.Reading;
import java.util.Map;
import java.util.TreeMap;

/**
 * Whole-stream totals per feeder, emitted on {@link #flush()} (ordered by feeder id). The window of
 * each result spans the first to the last event time seen for the feeder (end exclusive, +1 ms).
 * Used by the nightly settlement batch.
 */
public class CumulativeAggregator implements WindowAggregator {
    private final WindowSink sink;
    private final Map<String, Accumulator> totals = new TreeMap<>();
    private final Map<String, long[]> spans = new TreeMap<>();

    public CumulativeAggregator(WindowSink sink) {
        this.sink = sink;
    }

    @Override
    public void accept(Reading r) {
        totals.computeIfAbsent(r.feederId(), k -> new Accumulator()).add(r.valueKw());
        spans.merge(r.feederId(), new long[] {r.timestampMillis(), r.timestampMillis()},
            (a, b) -> new long[] {Math.min(a[0], b[0]), Math.max(a[1], b[1])});
    }

    @Override
    public void flush() {
        for (Map.Entry<String, Accumulator> e : totals.entrySet()) {
            long[] span = spans.get(e.getKey());
            sink.emit(e.getValue().toResult(e.getKey(), span[0], span[1] + 1));
        }
        totals.clear();
        spans.clear();
    }
}
