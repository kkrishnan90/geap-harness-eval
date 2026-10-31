package com.gridline.telemetry.report;

import static testkit.Assert.*;

import com.gridline.telemetry.window.WindowResult;
import java.util.List;
import testkit.Test;

public class FeederLoadReportTest {
    private final List<WindowResult> results = List.of(
        new WindowResult("SUB12-F04", 0, 60_000, 4, 2000, 400, 600),
        new WindowResult("SUB12-F05", 0, 60_000, 2, 1900, 900, 1000));

    @Test
    public void rendersCsv() {
        List<String> lines = new FeederLoadReport(1000).render(results);
        assertEquals(FeederLoadReport.HEADER, lines.get(0));
        assertEquals("SUB12-F04,1970-01-01T00:00:00Z,1970-01-01T00:01:00Z,4,500.000,600.000,50.0", lines.get(1));
    }

    @Test
    public void overloadsAndPeak() {
        FeederLoadReport rep = new FeederLoadReport(1000);
        assertEquals(1, rep.overloads(results, 90).size());
        assertEquals("SUB12-F05", rep.peak(results).get().feederId());
        assertTrue(rep.peak(List.of()).isEmpty());
    }
}
