package com.gridline.telemetry.window;

import static testkit.Assert.*;

import com.gridline.telemetry.model.Reading;
import java.util.List;
import testkit.Test;

public class TumblingWindowTest {
    /** 2026-03-01T10:15:00Z, aligned to whole minutes. */
    static final long T0 = 1_772_360_100_000L;
    static final long MIN = 60_000L;

    static void assertWindow(WindowResult r, String feeder, long start, long end, long count, double sum, double min, double max) {
        String ctx = r.toString();
        assertEquals(feeder, r.feederId(), ctx);
        assertEquals(start, r.windowStart(), "start " + ctx);
        assertEquals(end, r.windowEnd(), "end " + ctx);
        assertEquals(count, r.count(), "count " + ctx);
        assertEquals(sum, r.sumKw(), 1e-9, "sum " + ctx);
        assertEquals(min, r.minKw(), 1e-9, "min " + ctx);
        assertEquals(max, r.maxKw(), 1e-9, "max " + ctx);
    }

    @Test
    public void emitsWhenWatermarkPassesWindowEnd() {
        CollectingSink sink = new CollectingSink();
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.tumbling(MIN), 0, sink, r -> fail("late " + r));
        agg.accept(Reading.good("SUB12-F04", T0 + 1_000, 10));
        agg.accept(Reading.good("SUB12-F04", T0 + 30_000, 20));
        agg.accept(Reading.good("SUB12-F04", T0 + 59_999, 30));
        assertTrue(sink.results().isEmpty(), "window still open: " + sink.results());
        agg.accept(Reading.good("SUB12-F04", T0 + MIN, 5));
        List<WindowResult> rs = sink.results();
        assertEquals(1, rs.size());
        assertWindow(rs.get(0), "SUB12-F04", T0, T0 + MIN, 3, 60, 10, 30);
        assertEquals(20.0, rs.get(0).avgKw(), 1e-9, "avg");
        assertEquals(T0 + MIN, agg.watermark());
        assertEquals(1, agg.openWindowCount());
    }

    @Test
    public void windowsAreAlignedToEpoch() {
        CollectingSink sink = new CollectingSink();
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.tumbling(MIN), 0, sink, r -> { });
        agg.accept(Reading.good("F1", T0 + 125_000, 1.5));
        agg.flush();
        assertEquals(1, sink.results().size());
        assertWindow(sink.results().get(0), "F1", T0 + 2 * MIN, T0 + 3 * MIN, 1, 1.5, 1.5, 1.5);
    }

    @Test
    public void emissionOrderedByWindowEndThenFeeder() {
        CollectingSink sink = new CollectingSink();
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.tumbling(MIN), 0, sink, r -> { });
        agg.accept(Reading.good("SUB12-F05", T0 + 1_000, 1));
        agg.accept(Reading.good("SUB03-F01", T0 + 2_000, 2));
        agg.accept(Reading.good("SUB12-F04", T0 + 3_000, 3));
        agg.accept(Reading.good("SUB99-F09", T0 + 61_000, 4));
        agg.accept(Reading.good("SUB01-F01", T0 + 130_000, 5));
        List<WindowResult> rs = sink.results();
        assertEquals(4, rs.size(), rs.toString());
        assertEquals("SUB03-F01", rs.get(0).feederId());
        assertEquals("SUB12-F04", rs.get(1).feederId());
        assertEquals("SUB12-F05", rs.get(2).feederId());
        assertWindow(rs.get(3), "SUB99-F09", T0 + MIN, T0 + 2 * MIN, 1, 4, 4, 4);
        agg.flush();
        assertWindow(sink.results().get(4), "SUB01-F01", T0 + 2 * MIN, T0 + 3 * MIN, 1, 5, 5, 5);
    }

    @Test
    public void emptyWindowsAreNotEmitted() {
        CollectingSink sink = new CollectingSink();
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.tumbling(MIN), 0, sink, r -> { });
        agg.accept(Reading.good("F1", T0 + 1_000, 7));
        agg.accept(Reading.good("F1", T0 + 250_000, 9));
        assertEquals(1, sink.results().size(), sink.results().toString());
        agg.flush();
        List<WindowResult> rs = sink.results();
        assertEquals(2, rs.size(), rs.toString());
        assertEquals(T0 + 4 * MIN, rs.get(1).windowStart());
    }

    @Test
    public void allowedLatenessHoldsWindowOpen() {
        CollectingSink sink = new CollectingSink();
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.tumbling(MIN), 10_000, sink, r -> fail("late " + r));
        agg.accept(Reading.good("F1", T0 + 50_000, 1));
        agg.accept(Reading.good("F1", T0 + 65_000, 2));
        assertEquals(T0 + 55_000, agg.watermark());
        assertTrue(sink.results().isEmpty(), "watermark has not passed the first window");
        agg.accept(Reading.good("F1", T0 + 58_000, 4));
        agg.accept(Reading.good("F1", T0 + 70_000, 8));
        List<WindowResult> rs = sink.results();
        assertEquals(1, rs.size(), rs.toString());
        assertWindow(rs.get(0), "F1", T0, T0 + MIN, 2, 5, 1, 4);
        agg.flush();
        assertWindow(sink.results().get(1), "F1", T0 + MIN, T0 + 2 * MIN, 2, 10, 2, 8);
        assertEquals(0L, agg.lateEventCount());
    }

    @Test
    public void flushEmitsEverythingAndClearsState() {
        CollectingSink sink = new CollectingSink();
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.tumbling(MIN), 120_000, sink, r -> { });
        agg.accept(Reading.good("F2", T0 + 61_000, 1));
        agg.accept(Reading.good("F1", T0 + 1_000, 2));
        agg.accept(Reading.good("F2", T0 + 2_000, 3));
        assertEquals(3, agg.openWindowCount());
        agg.flush();
        List<WindowResult> rs = sink.results();
        assertEquals(3, rs.size(), rs.toString());
        assertWindow(rs.get(0), "F1", T0, T0 + MIN, 1, 2, 2, 2);
        assertWindow(rs.get(1), "F2", T0, T0 + MIN, 1, 3, 3, 3);
        assertWindow(rs.get(2), "F2", T0 + MIN, T0 + 2 * MIN, 1, 1, 1, 1);
        assertEquals(0, agg.openWindowCount());
    }

    @Test
    public void reverseFlowStatistics() {
        CollectingSink sink = new CollectingSink();
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.tumbling(MIN), 0, sink, r -> { });
        agg.accept(Reading.good("PV-FEEDER", T0 + 1, -3.5));
        agg.accept(Reading.good("PV-FEEDER", T0 + 2, 1.5));
        agg.accept(Reading.good("PV-FEEDER", T0 + 3, -0.25));
        agg.flush();
        WindowResult r = sink.results().get(0);
        assertWindow(r, "PV-FEEDER", T0, T0 + MIN, 3, -2.25, -3.5, 1.5);
        assertEquals(-0.75, r.avgKw(), 1e-9, "avg");
    }

    @Test
    public void stateStaysBoundedOnLongStream() {
        CollectingSink sink = new CollectingSink();
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.tumbling(MIN), 5_000, sink, r -> { });
        int maxOpen = 0;
        for (int i = 0; i < 12_000; i++) {
            agg.accept(Reading.good("F" + (i % 3), T0 + i * 1_000L, 1));
            maxOpen = Math.max(maxOpen, agg.openWindowCount());
        }
        assertTrue(maxOpen <= 6, "open windows should be bounded, max was " + maxOpen);
        assertEquals(3 * 199, sink.results().size());
        for (WindowResult r : sink.results()) assertEquals(20L, r.count(), r.toString());
    }
}
