package com.brightmart.loyalty;

import static testkit.Assert.*;

import com.brightmart.loyalty.model.PointsEntry;
import com.brightmart.loyalty.points.PointsBalance;
import com.brightmart.loyalty.points.PointsExpiryPolicy;
import com.brightmart.loyalty.statement.StatementFormatter;
import java.util.Arrays;
import java.util.Date;
import testkit.Test;

/** Legacy java.util.Date based tests (to be migrated together with the API). */
public class DateHandlingTest {
    private static final long DAY = 24L * 3600 * 1000;

    @Test
    public void freshPointsAreAvailable() {
        Date now = new Date(1_770_000_000_000L);
        PointsBalance b = new PointsBalance(new PointsExpiryPolicy());
        int avail = b.available(Arrays.asList(
                new PointsEntry(new Date(now.getTime() - 10 * DAY), 300, "STORE"),
                new PointsEntry(new Date(now.getTime() - 5 * DAY), -100, "REDEEM")), now);
        assertEquals(200, avail);
    }

    @Test
    public void oldPointsExpire() {
        Date now = new Date(1_770_000_000_000L);
        PointsBalance b = new PointsBalance(new PointsExpiryPolicy());
        int avail = b.available(Arrays.asList(new PointsEntry(new Date(now.getTime() - 800 * DAY), 300, "STORE")), now);
        assertEquals(0, avail);
    }

    @Test
    public void statementLineShape() {
        String line = new StatementFormatter().formatLine(new PointsEntry(new Date(1_770_000_000_000L), 120, "STORE"));
        assertTrue(line.matches("\\d{4}-\\d{2}-\\d{2}    \\+120  STORE"), line);
    }
}
