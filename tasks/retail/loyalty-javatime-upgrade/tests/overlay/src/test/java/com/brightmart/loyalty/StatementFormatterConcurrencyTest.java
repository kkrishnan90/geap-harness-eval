package com.brightmart.loyalty;

import static testkit.Assert.*;

import com.brightmart.loyalty.model.PointsEntry;
import com.brightmart.loyalty.statement.StatementFormatter;
import java.time.Instant;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.concurrent.CyclicBarrier;
import java.util.concurrent.atomic.AtomicReference;
import testkit.Test;

public class StatementFormatterConcurrencyTest {
    private static final ZoneId[] ZONES = {ZoneId.of("Europe/London"), ZoneId.of("Asia/Tokyo"),
            ZoneId.of("Australia/Sydney"), ZoneId.of("Europe/Dublin"), ZoneId.of("Pacific/Auckland")};

    @Test
    public void formatsInMemberZone() {
        StatementFormatter f = new StatementFormatter();
        Instant t = Instant.parse("2026-03-31T20:00:00Z");
        assertEquals("2026-03-31", f.formatDate(t, ZoneId.of("Europe/London")));
        assertEquals("2026-04-01", f.formatDate(t, ZoneId.of("Asia/Tokyo")));
        assertEquals("2026-04-01    +120  STORE", f.formatLine(new PointsEntry(t, 120, "STORE"), ZoneId.of("Asia/Tokyo")));
        assertEquals("2026-03-31   -1500  REDEEM", f.formatLine(new PointsEntry(t, -1500, "REDEEM"), ZoneId.of("Europe/London")));
    }

    @Test(timeoutMillis = 60_000)
    public void sharedFormatterIsThreadSafe() throws Exception {
        final StatementFormatter shared = new StatementFormatter();
        final int threads = 16, perThread = 4000;
        final CyclicBarrier start = new CyclicBarrier(threads);
        final AtomicReference<String> firstError = new AtomicReference<>();
        List<Thread> workers = new ArrayList<>();
        for (int w = 0; w < threads; w++) {
            final long seed = 1000L + w;
            Thread t = new Thread(() -> {
                Random rnd = new Random(seed);
                try {
                    start.await();
                    for (int i = 0; i < perThread && firstError.get() == null; i++) {
                        Instant instant = Instant.ofEpochSecond(1_600_000_000L + (long) rnd.nextInt(400_000_000));
                        ZoneId zone = ZONES[rnd.nextInt(ZONES.length)];
                        String expected = instant.atZone(zone).toLocalDate().toString();
                        String actual = shared.formatDate(instant, zone);
                        if (!expected.equals(actual)) {
                            firstError.compareAndSet(null, instant + " in " + zone + ": expected " + expected + " got " + actual);
                        }
                    }
                } catch (Throwable e) {
                    firstError.compareAndSet(null, e.toString());
                }
            });
            workers.add(t);
            t.start();
        }
        for (Thread t : workers) t.join(50_000);
        assertNull(firstError.get(), "concurrent formatting produced a wrong date");
    }
}
