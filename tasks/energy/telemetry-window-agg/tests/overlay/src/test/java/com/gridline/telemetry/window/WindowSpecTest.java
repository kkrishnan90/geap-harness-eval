package com.gridline.telemetry.window;

import static testkit.Assert.*;

import testkit.Test;

public class WindowSpecTest {
    @Test
    public void tumblingHasSlideEqualToSize() {
        WindowSpec s = WindowSpec.tumbling(60_000);
        assertEquals(60_000L, s.sizeMillis());
        assertEquals(60_000L, s.slideMillis());
    }

    @Test
    public void slidingKeepsSizeAndSlide() {
        WindowSpec s = WindowSpec.sliding(900_000, 300_000);
        assertEquals(900_000L, s.sizeMillis());
        assertEquals(300_000L, s.slideMillis());
    }

    @Test
    public void invalidSpecsRejected() {
        assertThrows(IllegalArgumentException.class, () -> WindowSpec.tumbling(0));
        assertThrows(IllegalArgumentException.class, () -> WindowSpec.tumbling(-5));
        assertThrows(IllegalArgumentException.class, () -> WindowSpec.sliding(60_000, 0));
        assertThrows(IllegalArgumentException.class, () -> WindowSpec.sliding(10_000, 20_000));
        assertThrows(IllegalArgumentException.class, () -> WindowSpec.sliding(60_000, 25_000));
    }

    @Test
    public void aggregatorRejectsNegativeLateness() {
        assertThrows(IllegalArgumentException.class,
            () -> new EventTimeWindowAggregator(WindowSpec.tumbling(1000), -1, r -> { }, r -> { }));
    }
}
