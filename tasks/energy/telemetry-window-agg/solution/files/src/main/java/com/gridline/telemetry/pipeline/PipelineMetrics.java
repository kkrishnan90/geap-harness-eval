package com.gridline.telemetry.pipeline;

import java.util.concurrent.atomic.AtomicLong;

/** Counters exported to Prometheus by the service wrapper. */
public class PipelineMetrics {
    private final AtomicLong received = new AtomicLong();
    private final AtomicLong filtered = new AtomicLong();
    private final AtomicLong aggregated = new AtomicLong();
    private final AtomicLong rejected = new AtomicLong();

    public void incrementReceived() { received.incrementAndGet(); }

    public void incrementFiltered() { filtered.incrementAndGet(); }

    public void incrementAggregated() { aggregated.incrementAndGet(); }

    public void incrementRejected() { rejected.incrementAndGet(); }

    public long received() { return received.get(); }

    public long filtered() { return filtered.get(); }

    public long aggregated() { return aggregated.get(); }

    /** Readings refused by the bounded buffer (backpressure). */
    public long rejected() { return rejected.get(); }
}
