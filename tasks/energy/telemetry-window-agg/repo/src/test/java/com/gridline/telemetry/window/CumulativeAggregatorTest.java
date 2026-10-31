package com.gridline.telemetry.window;

import static testkit.Assert.*;

import com.gridline.telemetry.model.Reading;
import java.util.List;
import testkit.Test;

public class CumulativeAggregatorTest {
    @Test
    public void totalsPerFeederOnFlush() {
        CollectingSink sink = new CollectingSink();
        CumulativeAggregator agg = new CumulativeAggregator(sink);
        agg.accept(Reading.good("F2", 5_000, 10));
        agg.accept(Reading.good("F1", 2_000, 4));
        agg.accept(Reading.good("F2", 1_000, -2));
        agg.accept(Reading.good("F1", 9_000, 6));
        assertTrue(sink.results().isEmpty(), "nothing before flush");
        agg.flush();
        List<WindowResult> rs = sink.results();
        assertEquals(2, rs.size());
        WindowResult f1 = rs.get(0);
        assertEquals("F1", f1.feederId());
        assertEquals(2_000L, f1.windowStart());
        assertEquals(9_001L, f1.windowEnd());
        assertEquals(5.0, f1.avgKw(), 1e-12, "avg");
        WindowResult f2 = rs.get(1);
        assertEquals(-2.0, f2.minKw(), 1e-12, "min");
        assertEquals(10.0, f2.maxKw(), 1e-12, "max");
        assertEquals(2L, f2.count());
    }

    @Test
    public void energyFromAverage() {
        WindowResult r = new WindowResult("F1", 0, 900_000, 3, 300, 90, 110);
        assertEquals(25.0, r.energyKwh(), 1e-9, "15 min at 100 kW");
    }
}
