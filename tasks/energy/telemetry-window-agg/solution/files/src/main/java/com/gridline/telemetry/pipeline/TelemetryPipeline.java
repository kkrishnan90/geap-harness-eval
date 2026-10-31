package com.gridline.telemetry.pipeline;

import com.gridline.telemetry.buffer.BoundedReadingBuffer;
import com.gridline.telemetry.model.Reading;
import com.gridline.telemetry.quality.QualityFilter;
import com.gridline.telemetry.window.WindowAggregator;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * Glue between ingest and aggregation: [bounded buffer ->] quality filter -> aggregator, with
 * metrics.
 *
 * <p>Batch mode: {@link #process(List)}. Buffered mode (when built with a
 * {@link BoundedReadingBuffer}): ingest threads call {@link #submit}, the consumer calls
 * {@link #drain()}.
 */
public class TelemetryPipeline {
    private final BoundedReadingBuffer buffer;
    private final QualityFilter filter;
    private final WindowAggregator aggregator;
    private final PipelineMetrics metrics;

    public TelemetryPipeline(QualityFilter filter, WindowAggregator aggregator, PipelineMetrics metrics) {
        this(null, filter, aggregator, metrics);
    }

    public TelemetryPipeline(BoundedReadingBuffer buffer, QualityFilter filter, WindowAggregator aggregator, PipelineMetrics metrics) {
        this.buffer = buffer;
        this.filter = filter;
        this.aggregator = aggregator;
        this.metrics = metrics;
    }

    public void process(List<Reading> batch) {
        for (Reading r : batch) {
            metrics.incrementReceived();
            handle(r);
        }
    }

    /** Offers a reading to the buffer. Returns false (and counts it as rejected) if refused. */
    public boolean submit(Reading r, long timeout, TimeUnit unit) throws InterruptedException {
        if (buffer == null) throw new IllegalStateException("pipeline has no buffer");
        metrics.incrementReceived();
        boolean ok = buffer.offer(r, timeout, unit);
        if (!ok) metrics.incrementRejected();
        return ok;
    }

    /** Processes everything currently buffered on the calling thread; returns how many readings were taken. */
    public int drain() {
        if (buffer == null) return 0;
        int n = 0;
        Reading r;
        while ((r = buffer.poll()) != null) {
            handle(r);
            n++;
        }
        return n;
    }

    private void handle(Reading r) {
        if (!filter.accept(r)) {
            metrics.incrementFiltered();
            return;
        }
        aggregator.accept(r);
        metrics.incrementAggregated();
    }

    /** End of stream: drains the buffer (if any), then flushes the aggregator. */
    public void close() {
        drain();
        aggregator.flush();
    }

    public PipelineMetrics metrics() {
        return metrics;
    }
}
