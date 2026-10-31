package com.brightmart.loyalty;

import static testkit.Assert.*;

import com.brightmart.loyalty.model.PointsEntry;
import com.brightmart.loyalty.points.PointsBalance;
import com.brightmart.loyalty.points.PointsExpiryPolicy;
import com.brightmart.loyalty.statement.StatementFormatter;
import java.time.Instant;
import java.time.ZoneId;
import java.time.temporal.ChronoUnit;
import java.util.Arrays;
import testkit.Test;

public class DateHandlingTest {
    private static final ZoneId LONDON = ZoneId.of("Europe/London");
    private static final Instant NOW = Instant.parse("2026-02-02T02:40:00Z");

    @Test
    public void freshPointsAreAvailable() {
        PointsBalance b = new PointsBalance(new PointsExpiryPolicy());
        int avail = b.available(Arrays.asList(
                new PointsEntry(NOW.minus(10, ChronoUnit.DAYS), 300, "STORE"),
                new PointsEntry(NOW.minus(5, ChronoUnit.DAYS), -100, "REDEEM")), NOW, LONDON);
        assertEquals(200, avail);
    }

    @Test
    public void oldPointsExpire() {
        PointsBalance b = new PointsBalance(new PointsExpiryPolicy());
        int avail = b.available(Arrays.asList(new PointsEntry(NOW.minus(800, ChronoUnit.DAYS), 300, "STORE")), NOW, LONDON);
        assertEquals(0, avail);
    }

    @Test
    public void statementLineShape() {
        String line = new StatementFormatter().formatLine(new PointsEntry(NOW, 120, "STORE"), LONDON);
        assertEquals("2026-02-02    +120  STORE", line);
    }
}
