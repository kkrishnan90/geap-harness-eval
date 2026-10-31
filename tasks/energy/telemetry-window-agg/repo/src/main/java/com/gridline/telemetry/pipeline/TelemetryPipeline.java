package com.gridline.telemetry.pipeline;

import com.gridline.telemetry.model.Reading;
import com.gridline.telemetry.quality.QualityFilter;
import com.gridline.telemetry.window.WindowAggregator;
import java.util.List;

/**
 * Glue between ingest and aggregation: quality filter -> aggregator, with metrics.
 *
 * <p>Today the service wrapper calls {@link #process(List)} with whatever the Kafka consumer
 * polled; batches are unbounded.
 */
public class TelemetryPipeline {
    private final QualityFilter filter;
    private final WindowAggregator aggregator;
    private final PipelineMetrics metrics;

    public TelemetryPipeline(QualityFilter filter, WindowAggregator aggregator, PipelineMetrics metrics) {
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

    private void handle(Reading r) {
        if (!filter.accept(r)) {
            metrics.incrementFiltered();
            return;
        }
        aggregator.accept(r);
        metrics.incrementAggregated();
    }

    /** End of stream. */
    public void close() {
        aggregator.flush();
    }

    public PipelineMetrics metrics() {
        return metrics;
    }
}
