package com.gridline.telemetry.window;

import static testkit.Assert.*;

import com.gridline.telemetry.model.Reading;
import java.util.ArrayList;
import java.util.List;
import testkit.Test;

public class LateEventTest {
    static final long T0 = 1_772_360_100_000L;
    static final long MIN = 60_000L;

    @Test
    public void lateReadingGoesToSideOutput() {
        CollectingSink sink = new CollectingSink();
        List<Reading> late = new ArrayList<>();
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.tumbling(MIN), 0, sink, late::add);
        agg.accept(Reading.good("F1", T0 + 70_000, 1));
        Reading stale = Reading.good("F1", T0 + 10_000, 99);
        agg.accept(stale);
        assertEquals(1, late.size());
        assertEquals(stale, late.get(0));
        assertEquals(1L, agg.lateEventCount());
        agg.flush();
        List<WindowResult> rs = sink.results();
        assertEquals(1, rs.size(), rs.toString());
        assertEquals(T0 + MIN, rs.get(0).windowStart());
        assertEquals(1.0, rs.get(0).sumKw(), 1e-9, "late value must not be aggregated");
    }

    @Test
    public void lateReadingDoesNotReopenEmittedWindow() {
        CollectingSink sink = new CollectingSink();
        List<Reading> late = new ArrayList<>();
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.tumbling(MIN), 0, sink, late::add);
        agg.accept(Reading.good("F1", T0 + 1_000, 5));
        agg.accept(Reading.good("F1", T0 + 61_000, 6));
        assertEquals(1, sink.results().size());
        agg.accept(Reading.good("F1", T0 + 2_000, 7));
        agg.accept(Reading.good("F2", T0 + 59_999, 8));
        assertEquals(2, late.size());
        agg.flush();
        List<WindowResult> rs = sink.results();
        assertEquals(2, rs.size(), rs.toString());
        assertEquals(1L, rs.get(0).count());
        assertEquals(5.0, rs.get(0).sumKw(), 1e-9, "first window unchanged");
        assertEquals(1L, rs.get(1).count());
        assertEquals(2L, agg.lateEventCount());
    }

    @Test
    public void readingExactlyAtWatermarkBoundaryIsLate() {
        CollectingSink sink = new CollectingSink();
        List<Reading> late = new ArrayList<>();
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.tumbling(MIN), 5_000, sink, late::add);
        agg.accept(Reading.good("F1", T0 + 65_000, 1));   // watermark T0+60s closes [T0, T0+60s)
        agg.accept(Reading.good("F1", T0 + 59_999, 2));   // its window ended at the watermark
        agg.accept(Reading.good("F1", T0 + 60_000, 3));   // next window still open
        assertEquals(1, late.size());
        assertEquals(T0 + 59_999, late.get(0).timestampMillis());
        agg.flush();
        assertEquals(1, sink.results().size());
        assertEquals(2L, sink.results().get(0).count());
    }

    @Test
    public void outOfOrderWithinLatenessIsNotLate() {
        CollectingSink sink = new CollectingSink();
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.tumbling(MIN), 30_000, sink, r -> fail("late " + r));
        agg.accept(Reading.good("F1", T0 + 80_000, 1));
        agg.accept(Reading.good("F1", T0 + 55_000, 2));
        agg.accept(Reading.good("F1", T0 + 95_000, 3));
        assertEquals(1, sink.results().size());
        assertEquals(2.0, sink.results().get(0).sumKw(), 1e-9, "sum");
        assertEquals(0L, agg.lateEventCount());
    }

    @Test
    public void slidingReadingPartiallyLateIsKeptForOpenWindows() {
        CollectingSink sink = new CollectingSink();
        List<Reading> late = new ArrayList<>();
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.sliding(MIN, 15_000), 0, sink, late::add);
        agg.accept(Reading.good("F1", T0 + 60_000, 1));
        agg.accept(Reading.good("F1", T0 + 20_000, 2));
        assertTrue(late.isEmpty(), "still belongs to an open window");
        assertEquals(0L, agg.lateEventCount());
        agg.accept(Reading.good("F1", T0 + 14_000, 4));
        assertEquals(1, late.size());
        agg.flush();
        List<WindowResult> rs = sink.results();
        assertEquals(4, rs.size(), rs.toString());
        assertEquals(T0 + 15_000, rs.get(0).windowStart());
        assertEquals(2L, rs.get(0).count());
        assertEquals(3.0, rs.get(0).sumKw(), 1e-9, "sum");
    }

    @Test
    public void watermarkNeverMovesBackwards() {
        EventTimeWindowAggregator agg = new EventTimeWindowAggregator(WindowSpec.tumbling(MIN), 10_000, r -> { }, r -> { });
        assertEquals(Long.MIN_VALUE, agg.watermark());
        agg.accept(Reading.good("F1", T0 + 50_000, 1));
        assertEquals(T0 + 40_000, agg.watermark());
        agg.accept(Reading.good("F1", T0 + 20_000, 1));
        assertEquals(T0 + 40_000, agg.watermark());
        agg.accept(Reading.good("F2", T0 + 90_000, 1));
        assertEquals(T0 + 80_000, agg.watermark());
    }
}
