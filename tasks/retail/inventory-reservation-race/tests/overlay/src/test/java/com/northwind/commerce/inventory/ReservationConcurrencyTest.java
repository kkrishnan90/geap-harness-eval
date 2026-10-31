package com.northwind.commerce.inventory;

import static testkit.Assert.*;

import java.time.Clock;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.CyclicBarrier;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.function.IntFunction;
import testkit.Test;

/** Concurrency acceptance tests for ReservationService (hidden verifier suite). */
public class ReservationConcurrencyTest {

    /** Outcome of one concurrent call: a value or the exception it threw. */
    static final class Outcome<T> {
        final T value;
        final Throwable error;

        Outcome(T value, Throwable error) {
            this.value = value;
            this.error = error;
        }
    }

    private static ExecutorService pool(int n) {
        return Executors.newFixedThreadPool(n, r -> {
            Thread t = new Thread(r, "checkout-worker");
            t.setDaemon(true);
            return t;
        });
    }

    /** Runs {@code n} calls released simultaneously by a barrier; returns their outcomes in index order. */
    private static <T> List<Outcome<T>> race(ExecutorService pool, int n, IntFunction<Callable<T>> work) throws Exception {
        CyclicBarrier start = new CyclicBarrier(n);
        List<Future<T>> futures = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            Callable<T> c = work.apply(i);
            futures.add(pool.submit(() -> {
                start.await(10, TimeUnit.SECONDS);
                return c.call();
            }));
        }
        List<Outcome<T>> out = new ArrayList<>();
        for (Future<T> f : futures) {
            try {
                out.add(new Outcome<>(f.get(20, TimeUnit.SECONDS), null));
            } catch (ExecutionException e) {
                out.add(new Outcome<>(null, e.getCause()));
            }
        }
        return out;
    }

    private static int activeQuantity(ReservationService s, String sku) {
        int sum = 0;
        for (Reservation r : s.activeReservations(sku)) sum += r.getQuantity();
        return sum;
    }

    @Test(timeoutMillis = 90_000)
    public void sameSkuIsNeverOversold() throws Exception {
        ExecutorService pool = pool(16);
        try {
            for (int round = 0; round < 300; round++) {
                InMemoryInventoryRepository repo = new InMemoryInventoryRepository().put(StockRecord.of("CONSOLE-X", 5));
                ReservationService s = new ReservationService(repo);
                List<Outcome<Reservation>> res = race(pool, 16, i -> () -> s.reserve("ORD-" + i, "CONSOLE-X", 1));
                int ok = 0;
                for (Outcome<Reservation> o : res) {
                    if (o.error == null) ok++;
                    else if (!(o.error instanceof InsufficientStockException)) throw new AssertionError("unexpected", o.error);
                }
                StockRecord rec = repo.load("CONSOLE-X").get();
                assertEquals(5, ok, "round " + round + ": successful reservations");
                assertEquals(5, rec.getReserved(), "round " + round + ": reserved units");
                assertEquals(0, rec.available(), "round " + round + ": available");
                assertEquals(5, s.activeReservations("CONSOLE-X").size(), "round " + round + ": active reservations");
            }
        } finally {
            pool.shutdownNow();
        }
    }

    @Test(timeoutMillis = 90_000)
    public void mixedQuantitiesKeepStockConsistent() throws Exception {
        ExecutorService pool = pool(12);
        try {
            for (int round = 0; round < 100; round++) {
                InMemoryInventoryRepository repo = new InMemoryInventoryRepository().put(StockRecord.of("SNEAKER-42", 40));
                ReservationService s = new ReservationService(repo);
                List<Outcome<Integer>> res = race(pool, 12, i -> () -> {
                    int got = 0;
                    for (int k = 0; k < 5; k++) {
                        int q = (i + k) % 3 + 1;
                        try {
                            s.reserve("ORD-" + i + "-" + k, "SNEAKER-42", q);
                            got += q;
                        } catch (InsufficientStockException e) {
                            // sold out for this quantity
                        }
                    }
                    return got;
                });
                int reservedByCallers = 0;
                for (Outcome<Integer> o : res) {
                    if (o.error != null) throw new AssertionError("unexpected", o.error);
                    reservedByCallers += o.value;
                }
                StockRecord rec = repo.load("SNEAKER-42").get();
                assertTrue(rec.getReserved() <= 40, "round " + round + ": oversold " + rec);
                assertEquals(reservedByCallers, rec.getReserved(), "round " + round + ": reserved vs confirmed");
                assertEquals(reservedByCallers, activeQuantity(s, "SNEAKER-42"), "round " + round + ": active reservations");
            }
        } finally {
            pool.shutdownNow();
        }
    }

    @Test(timeoutMillis = 90_000)
    public void concurrentReleaseReturnsUnitsExactlyOnce() throws Exception {
        ExecutorService pool = pool(8);
        try {
            for (int round = 0; round < 300; round++) {
                InventoryAuditLog audit = new InventoryAuditLog();
                InMemoryInventoryRepository repo = new InMemoryInventoryRepository().put(StockRecord.of("LAMP-OAK", 3));
                ReservationService s = new ReservationService(repo, new ReservationStore(), audit, Clock.systemUTC());
                Reservation r = s.reserve("ORD-1", "LAMP-OAK", 2);
                List<Outcome<Boolean>> res = race(pool, 8, i -> () -> s.release(r.getId()));
                int released = 0;
                for (Outcome<Boolean> o : res) {
                    if (o.error != null) throw new AssertionError("unexpected", o.error);
                    if (o.value) released++;
                }
                assertEquals(1, released, "round " + round + ": release() returning true");
                assertEquals(1L, audit.count(InventoryAuditLog.Action.RELEASE), "round " + round + ": RELEASE audit lines");
                assertEquals(3, s.available("LAMP-OAK"), "round " + round + ": available");
                assertEquals(0, repo.load("LAMP-OAK").get().getReserved(), "round " + round + ": reserved");
            }
        } finally {
            pool.shutdownNow();
        }
    }

    @Test(timeoutMillis = 90_000)
    public void concurrentRetriesOfOneOrderLineReserveOnce() throws Exception {
        ExecutorService pool = pool(8);
        try {
            for (int round = 0; round < 300; round++) {
                InMemoryInventoryRepository repo = new InMemoryInventoryRepository().put(StockRecord.of("TV-55", 100));
                ReservationService s = new ReservationService(repo);
                List<Outcome<Reservation>> res = race(pool, 8, i -> () -> s.reserve("ORD-77", "TV-55", 2));
                Set<String> ids = new HashSet<>();
                for (Outcome<Reservation> o : res) {
                    if (o.error != null) throw new AssertionError("unexpected", o.error);
                    ids.add(o.value.getId());
                }
                assertEquals(1, ids.size(), "round " + round + ": distinct reservation ids for one order line");
                assertEquals(98, s.available("TV-55"), "round " + round + ": available");
                assertEquals(1, s.activeReservations("TV-55").size(), "round " + round + ": active reservations");
            }
        } finally {
            pool.shutdownNow();
        }
    }

    @Test(timeoutMillis = 90_000)
    public void commitReleaseAndReserveInterleaved() throws Exception {
        ExecutorService pool = pool(20);
        try {
            for (int round = 0; round < 150; round++) {
                InMemoryInventoryRepository repo = new InMemoryInventoryRepository().put(StockRecord.of("KETTLE", 30));
                ReservationService s = new ReservationService(repo);
                List<Reservation> pre = new ArrayList<>();
                for (int i = 0; i < 10; i++) pre.add(s.reserve("PRE-" + i, "KETTLE", 1));
                List<Outcome<Boolean>> res = race(pool, 20, i -> () -> {
                    if (i < 5) return s.commit(pre.get(i).getId());
                    if (i < 10) return s.release(pre.get(i).getId());
                    try {
                        s.reserve("NEW-" + i, "KETTLE", 2);
                        return true;
                    } catch (InsufficientStockException e) {
                        return false;
                    }
                });
                for (Outcome<Boolean> o : res) {
                    if (o.error != null) throw new AssertionError("unexpected", o.error);
                }
                StockRecord rec = repo.load("KETTLE").get();
                assertEquals(25, rec.getOnHand(), "round " + round + ": on hand after 5 commits");
                assertEquals(activeQuantity(s, "KETTLE"), rec.getReserved(), "round " + round + ": reserved vs active");
                assertEquals(20, rec.getReserved(), "round " + round + ": 10 new reservations of 2");
            }
        } finally {
            pool.shutdownNow();
        }
    }

    @Test(timeoutMillis = 90_000)
    public void restockIsNotLostUnderContention() throws Exception {
        ExecutorService pool = pool(16);
        try {
            for (int round = 0; round < 200; round++) {
                InMemoryInventoryRepository repo = new InMemoryInventoryRepository().put(StockRecord.of("PAINT-5L", 0));
                ReservationService s = new ReservationService(repo);
                race(pool, 16, i -> () -> {
                    s.restock("PAINT-5L", 3, "GRN-" + i);
                    return null;
                });
                assertEquals(48, repo.load("PAINT-5L").get().getOnHand(), "round " + round + ": on hand after 16 receipts");
            }
        } finally {
            pool.shutdownNow();
        }
    }

    /** Repository whose first load of one SKU parks until the test lets it continue. */
    static final class GatedRepository implements InventoryRepository {
        private final InventoryRepository delegate;
        private final String gatedSku;
        final CountDownLatch entered = new CountDownLatch(1);
        final CountDownLatch proceed = new CountDownLatch(1);
        private volatile boolean armed = true;

        GatedRepository(InventoryRepository delegate, String gatedSku) {
            this.delegate = delegate;
            this.gatedSku = gatedSku;
        }

        @Override
        public Optional<StockRecord> load(String sku) {
            if (armed && sku.equals(gatedSku)) {
                armed = false;
                entered.countDown();
                try {
                    proceed.await(15, TimeUnit.SECONDS);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }
            return delegate.load(sku);
        }

        @Override
        public void save(StockRecord record) {
            delegate.save(record);
        }

        @Override
        public boolean saveIfVersion(StockRecord record, long expectedVersion) {
            return delegate.saveIfVersion(record, expectedVersion);
        }

        @Override
        public Collection<String> skus() {
            return delegate.skus();
        }
    }

    @Test(timeoutMillis = 60_000)
    public void differentSkusDoNotWaitForEachOther() throws Exception {
        InMemoryInventoryRepository base = new InMemoryInventoryRepository()
            .put(StockRecord.of("SKU-A-GATED", 10))
            .put(StockRecord.of("SKU-B-FREE", 10));
        GatedRepository repo = new GatedRepository(base, "SKU-A-GATED");
        ReservationService s = new ReservationService(repo);
        ExecutorService pool = pool(2);
        try {
            Future<Reservation> slow = pool.submit(() -> s.reserve("ORD-A", "SKU-A-GATED", 1));
            assertTrue(repo.entered.await(10, TimeUnit.SECONDS), "reservation for SKU A never reached the store");
            Future<Reservation> fast = pool.submit(() -> s.reserve("ORD-B", "SKU-B-FREE", 1));
            Reservation b;
            try {
                b = fast.get(3, TimeUnit.SECONDS);
            } catch (java.util.concurrent.TimeoutException e) {
                throw new AssertionError("reservation for SKU B waited on an in-flight reservation for SKU A");
            } finally {
                repo.proceed.countDown();
            }
            assertEquals("SKU-B-FREE", b.getSku());
            assertEquals("SKU-A-GATED", slow.get(10, TimeUnit.SECONDS).getSku());
            assertEquals(9, s.available("SKU-A-GATED"));
            assertEquals(9, s.available("SKU-B-FREE"));
        } finally {
            repo.proceed.countDown();
            pool.shutdownNow();
        }
    }
}
