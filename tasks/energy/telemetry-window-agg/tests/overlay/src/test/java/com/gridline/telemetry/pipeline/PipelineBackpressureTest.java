package com.gridline.telemetry.pipeline;

import static testkit.Assert.*;

import com.gridline.telemetry.buffer.BoundedReadingBuffer;
import com.gridline.telemetry.buffer.OverflowPolicy;
import com.gridline.telemetry.model.Quality;
import com.gridline.telemetry.model.Reading;
import com.gridline.telemetry.quality.QualityFilter;
import com.gridline.telemetry.window.CollectingSink;
import com.gridline.telemetry.window.CumulativeAggregator;
import com.gridline.telemetry.window.EventTimeWindowAggregator;
import com.gridline.telemetry.window.WindowResult;
import com.gridline.telemetry.window.WindowSpec;
import java.util.List;
import java.util.concurrent.TimeUnit;
import testkit.Test;

public class PipelineBackpressureTest {
    static final long T0 = 1_772_360_100_000L;

    @Test
    public void submitThenDrainThroughFilterAndWindows() throws Exception {
        CollectingSink sink = new CollectingSink();
        PipelineMetrics m = new PipelineMetrics();
        BoundedReadingBuffer buf = new BoundedReadingBuffer(10, OverflowPolicy.REJECT);
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.tumbling(60_000), 0, sink, r -> { });
        TelemetryPipeline p = new TelemetryPipeline(buf, new QualityFilter(10_000), agg, m);
        assertTrue(p.submit(Reading.good("F1", T0 + 1_000, 100), 0, TimeUnit.MILLISECONDS));
        assertTrue(p.submit(new Reading("F1", T0 + 2_000, 100, Quality.BAD), 0, TimeUnit.MILLISECONDS));
        assertTrue(p.submit(Reading.good("F1", T0 + 61_000, 300), 0, TimeUnit.MILLISECONDS));
        assertEquals(3L, m.received());
        assertTrue(sink.results().isEmpty(), "nothing is processed before drain");
        assertEquals(3, p.drain());
        assertEquals(0, buf.size());
        assertEquals(1L, m.filtered());
        assertEquals(2L, m.aggregated());
        List<WindowResult> rs = sink.results();
        assertEquals(1, rs.size(), rs.toString());
        assertEquals(100.0, rs.get(0).sumKw(), 1e-9, "BAD reading filtered");
        assertEquals(0, p.drain());
    }

    @Test
    public void fullBufferRejectsAndCounts() throws Exception {
        PipelineMetrics m = new PipelineMetrics();
        BoundedReadingBuffer buf = new BoundedReadingBuffer(2, OverflowPolicy.REJECT);
        TelemetryPipeline p = new TelemetryPipeline(buf, new QualityFilter(10_000), new CumulativeAggregator(new CollectingSink()), m);
        assertTrue(p.submit(Reading.good("F1", 1, 1), 0, TimeUnit.MILLISECONDS));
        assertTrue(p.submit(Reading.good("F1", 2, 1), 0, TimeUnit.MILLISECONDS));
        assertFalse(p.submit(Reading.good("F1", 3, 1), 0, TimeUnit.MILLISECONDS));
        assertEquals(3L, m.received());
        assertEquals(1L, m.rejected());
        assertEquals(2, p.drain());
        assertEquals(2L, m.aggregated());
    }

    @Test
    public void dropOldestIsNotCountedAsRejected() throws Exception {
        PipelineMetrics m = new PipelineMetrics();
        BoundedReadingBuffer buf = new BoundedReadingBuffer(2, OverflowPolicy.DROP_OLDEST);
        CollectingSink sink = new CollectingSink();
        TelemetryPipeline p = new TelemetryPipeline(buf, new QualityFilter(10_000), new CumulativeAggregator(sink), m);
        for (int i = 1; i <= 5; i++) assertTrue(p.submit(Reading.good("F1", i, i), 0, TimeUnit.MILLISECONDS));
        assertEquals(0L, m.rejected());
        assertEquals(3L, buf.droppedCount());
        p.close();
        assertEquals(9.0, sink.results().get(0).sumKw(), 1e-9, "only readings 4 and 5 survive");
    }

    @Test
    public void closeDrainsBufferThenFlushes() throws Exception {
        CollectingSink sink = new CollectingSink();
        PipelineMetrics m = new PipelineMetrics();
        BoundedReadingBuffer buf = new BoundedReadingBuffer(8, OverflowPolicy.BLOCK);
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.tumbling(60_000), 0, sink, r -> { });
        TelemetryPipeline p = new TelemetryPipeline(buf, new QualityFilter(10_000), agg, m);
        p.submit(Reading.good("F2", T0 + 5_000, 2), 1, TimeUnit.SECONDS);
        p.submit(Reading.good("F1", T0 + 6_000, 1), 1, TimeUnit.SECONDS);
        p.close();
        List<WindowResult> rs = sink.results();
        assertEquals(2, rs.size(), rs.toString());
        assertEquals("F1", rs.get(0).feederId());
        assertEquals(0, buf.size());
    }

    @Test
    public void submitWithoutBufferIsAnError() {
        TelemetryPipeline p = new TelemetryPipeline(new QualityFilter(10), new CumulativeAggregator(new CollectingSink()), new PipelineMetrics());
        assertThrows(IllegalStateException.class, () -> p.submit(Reading.good("F1", 1, 1), 0, TimeUnit.MILLISECONDS));
    }
}
