package com.gridline.telemetry.window;

import static testkit.Assert.*;

import com.gridline.telemetry.model.Reading;
import java.util.List;
import testkit.Test;

public class SlidingWindowTest {
    static final long T0 = 1_772_360_100_000L;
    static final long SIZE = 60_000L;
    static final long SLIDE = 15_000L;

    @Test
    public void readingCountsInEveryOverlappingWindow() {
        CollectingSink sink = new CollectingSink();
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.sliding(SIZE, SLIDE), 0, sink, r -> { });
        agg.accept(Reading.good("F1", T0 + 20_000, 4));
        assertTrue(sink.results().isEmpty());
        agg.flush();
        List<WindowResult> rs = sink.results();
        assertEquals(4, rs.size(), rs.toString());
        long[] starts = {T0 - 30_000, T0 - 15_000, T0, T0 + 15_000};
        for (int i = 0; i < 4; i++) {
            assertEquals(starts[i], rs.get(i).windowStart(), "start of #" + i);
            assertEquals(starts[i] + SIZE, rs.get(i).windowEnd(), "end of #" + i);
            assertEquals(1L, rs.get(i).count());
            assertEquals(4.0, rs.get(i).sumKw(), 1e-9, "sum");
        }
    }

    @Test
    public void windowStartingExactlyAtReadingIncluded() {
        CollectingSink sink = new CollectingSink();
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.sliding(SIZE, SLIDE), 0, sink, r -> { });
        agg.accept(Reading.good("F1", T0, 1));
        agg.flush();
        List<WindowResult> rs = sink.results();
        assertEquals(4, rs.size(), rs.toString());
        assertEquals(T0 - 45_000, rs.get(0).windowStart());
        assertEquals(T0, rs.get(3).windowStart());
    }

    @Test
    public void progressiveEmissionOnSteadyStream() {
        CollectingSink sink = new CollectingSink();
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.sliding(SIZE, SLIDE), 0, sink, r -> fail("late"));
        for (int i = 0; i <= 24; i++) agg.accept(Reading.good("F1", T0 + i * 5_000L, i));
        // max event time T0+120s: windows ending at or before T0+120s are closed
        List<WindowResult> rs = sink.results();
        assertEquals(8, rs.size(), rs.toString());
        WindowResult full = rs.get(3);
        assertEquals(T0, full.windowStart());
        assertEquals(12L, full.count());
        assertEquals(66.0, full.sumKw(), 1e-9, "sum 0..11");
        assertEquals(0.0, full.minKw(), 1e-9, "min");
        assertEquals(11.0, full.maxKw(), 1e-9, "max");
        WindowResult last = rs.get(7);
        assertEquals(T0 + 60_000, last.windowStart());
        assertEquals(12L, last.count());
        assertEquals(12 * 17.5, last.sumKw(), 1e-9, "sum 12..23");
        for (int i = 1; i < rs.size(); i++) {
            assertTrue(rs.get(i).windowEnd() > rs.get(i - 1).windowEnd(), "ascending window ends");
        }
    }

    @Test
    public void feedersInterleavedPerWindowEnd() {
        CollectingSink sink = new CollectingSink();
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.sliding(30_000, 15_000), 0, sink, r -> { });
        agg.accept(Reading.good("B", T0 + 1_000, 1));
        agg.accept(Reading.good("A", T0 + 16_000, 2));
        agg.flush();
        List<WindowResult> rs = sink.results();
        // B in [T0-15s,T0+15s) and [T0,T0+30s); A in [T0,T0+30s) and [T0+15s,T0+45s)
        assertEquals(4, rs.size(), rs.toString());
        assertEquals("B", rs.get(0).feederId());
        assertEquals(T0 + 15_000, rs.get(0).windowEnd());
        assertEquals("A", rs.get(1).feederId());
        assertEquals(T0 + 30_000, rs.get(1).windowEnd());
        assertEquals("B", rs.get(2).feederId());
        assertEquals(T0 + 30_000, rs.get(2).windowEnd());
        assertEquals("A", rs.get(3).feederId());
        assertEquals(T0 + 45_000, rs.get(3).windowEnd());
    }
}
