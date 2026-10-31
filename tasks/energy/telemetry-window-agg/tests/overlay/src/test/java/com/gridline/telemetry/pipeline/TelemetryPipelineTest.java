package com.gridline.telemetry.pipeline;

import static testkit.Assert.*;

import com.gridline.telemetry.model.Quality;
import com.gridline.telemetry.model.Reading;
import com.gridline.telemetry.quality.QualityFilter;
import com.gridline.telemetry.window.CollectingSink;
import com.gridline.telemetry.window.CumulativeAggregator;
import java.util.List;
import testkit.Test;

public class TelemetryPipelineTest {
    @Test
    public void batchThroughFilterAndAggregator() {
        CollectingSink sink = new CollectingSink();
        PipelineMetrics m = new PipelineMetrics();
        TelemetryPipeline p = new TelemetryPipeline(new QualityFilter(1000), new CumulativeAggregator(sink), m);
        p.process(List.of(
            Reading.good("F1", 1, 100),
            new Reading("F1", 2, 100, Quality.BAD),
            Reading.good("F1", 3, 5000),
            Reading.good("F1", 4, 300)));
        p.close();
        assertEquals(4L, m.received());
        assertEquals(2L, m.filtered());
        assertEquals(2L, m.aggregated());
        assertEquals(1, sink.results().size());
        assertEquals(200.0, sink.results().get(0).avgKw(), 1e-12, "avg");
    }
}
