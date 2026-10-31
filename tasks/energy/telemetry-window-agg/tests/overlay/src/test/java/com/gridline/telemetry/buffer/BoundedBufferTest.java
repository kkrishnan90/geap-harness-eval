package com.gridline.telemetry.buffer;

import static testkit.Assert.*;

import com.gridline.telemetry.model.Reading;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import testkit.Test;

public class BoundedBufferTest {
    static Reading r(int i) {
        return Reading.good("F" + (i % 4), 1_000L * i, i);
    }

    static ExecutorService pool(int n) {
        return Executors.newFixedThreadPool(n, run -> {
            Thread t = new Thread(run, "ingest");
            t.setDaemon(true);
            return t;
        });
    }

    @Test
    public void fifoOrder() throws Exception {
        BoundedReadingBuffer b = new BoundedReadingBuffer(3, OverflowPolicy.REJECT);
        assertTrue(b.offer(r(1), 0, TimeUnit.MILLISECONDS));
        assertTrue(b.offer(r(2), 0, TimeUnit.MILLISECONDS));
        assertEquals(2, b.size());
        assertEquals(3, b.capacity());
        assertEquals(r(1), b.poll());
        assertEquals(r(2), b.poll());
        assertNull(b.poll(), "empty buffer");
    }

    @Test
    public void rejectPolicyRefusesImmediately() throws Exception {
        BoundedReadingBuffer b = new BoundedReadingBuffer(2, OverflowPolicy.REJECT);
        b.offer(r(1), 0, TimeUnit.MILLISECONDS);
        b.offer(r(2), 0, TimeUnit.MILLISECONDS);
        long t0 = System.nanoTime();
        assertFalse(b.offer(r(3), 5, TimeUnit.SECONDS), "full buffer must reject");
        assertTrue(System.nanoTime() - t0 < TimeUnit.SECONDS.toNanos(2), "REJECT must not wait");
        assertEquals(1L, b.rejectedCount());
        assertEquals(0L, b.droppedCount());
        assertEquals(2, b.size());
        assertEquals(r(1), b.poll());
    }

    @Test
    public void dropOldestEvictsHead() throws Exception {
        BoundedReadingBuffer b = new BoundedReadingBuffer(3, OverflowPolicy.DROP_OLDEST);
        for (int i = 1; i <= 5; i++) assertTrue(b.offer(r(i), 0, TimeUnit.MILLISECONDS), "DROP_OLDEST always accepts");
        assertEquals(3, b.size());
        assertEquals(2L, b.droppedCount());
        assertEquals(0L, b.rejectedCount());
        assertEquals(r(3), b.poll());
        assertEquals(r(4), b.poll());
        assertEquals(r(5), b.poll());
    }

    @Test
    public void blockPolicyTimesOut() throws Exception {
        BoundedReadingBuffer b = new BoundedReadingBuffer(1, OverflowPolicy.BLOCK);
        assertTrue(b.offer(r(1), 0, TimeUnit.MILLISECONDS));
        long t0 = System.nanoTime();
        assertFalse(b.offer(r(2), 150, TimeUnit.MILLISECONDS), "must give up after timeout");
        long waited = System.nanoTime() - t0;
        assertTrue(waited >= TimeUnit.MILLISECONDS.toNanos(100), "BLOCK must wait for the timeout, waited ns=" + waited);
        assertEquals(1L, b.rejectedCount());
        assertEquals(1, b.size());
    }

    @Test
    public void blockedProducerResumesWhenConsumerPolls() throws Exception {
        BoundedReadingBuffer b = new BoundedReadingBuffer(1, OverflowPolicy.BLOCK);
        b.offer(r(1), 0, TimeUnit.MILLISECONDS);
        ExecutorService pool = pool(1);
        try {
            CountDownLatch started = new CountDownLatch(1);
            Future<Boolean> producer = pool.submit(() -> {
                started.countDown();
                return b.offer(r(2), 10, TimeUnit.SECONDS);
            });
            assertTrue(started.await(5, TimeUnit.SECONDS));
            assertEquals(r(1), b.poll());
            assertTrue(producer.get(8, TimeUnit.SECONDS), "producer must be admitted once space frees up");
            assertEquals(r(2), b.poll());
            assertEquals(0L, b.rejectedCount());
        } finally {
            pool.shutdownNow();
        }
    }

    @Test
    public void invalidConstruction() {
        assertThrows(IllegalArgumentException.class, () -> new BoundedReadingBuffer(0, OverflowPolicy.BLOCK));
        assertThrows(IllegalArgumentException.class, () -> new BoundedReadingBuffer(-1, OverflowPolicy.REJECT));
    }

    @Test(timeoutMillis = 60_000)
    public void concurrentProducersLoseNothingUnderBlock() throws Exception {
        final int producers = 4, perProducer = 2_500, capacity = 16;
        BoundedReadingBuffer b = new BoundedReadingBuffer(capacity, OverflowPolicy.BLOCK);
        ExecutorService pool = pool(producers);
        try {
            List<Future<Integer>> fs = new ArrayList<>();
            for (int p = 0; p < producers; p++) {
                final int pid = p;
                fs.add(pool.submit(() -> {
                    int ok = 0;
                    for (int i = 0; i < perProducer; i++) {
                        if (b.offer(Reading.good("P" + pid, i, i), 20, TimeUnit.SECONDS)) ok++;
                    }
                    return ok;
                }));
            }
            int[] lastSeen = new int[producers];
            java.util.Arrays.fill(lastSeen, -1);
            int got = 0, maxSize = 0;
            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(40);
            while (got < producers * perProducer && System.nanoTime() < deadline) {
                maxSize = Math.max(maxSize, b.size());
                Reading x = b.poll();
                if (x == null) {
                    Thread.onSpinWait();
                    continue;
                }
                int pid = Integer.parseInt(x.feederId().substring(1));
                int seq = (int) x.timestampMillis();
                assertEquals(lastSeen[pid] + 1, seq, "per-producer FIFO for P" + pid);
                lastSeen[pid] = seq;
                got++;
            }
            assertEquals(producers * perProducer, got, "readings consumed");
            for (Future<Integer> f : fs) assertEquals(perProducer, (int) f.get(5, TimeUnit.SECONDS));
            assertTrue(maxSize <= capacity, "size exceeded capacity: " + maxSize);
            assertEquals(0L, b.rejectedCount());
            assertEquals(0L, b.droppedCount());
        } finally {
            pool.shutdownNow();
        }
    }
}
