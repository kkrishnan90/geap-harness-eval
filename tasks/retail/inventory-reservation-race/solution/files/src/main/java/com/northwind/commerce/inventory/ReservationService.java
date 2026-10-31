package com.northwind.commerce.inventory;

import java.time.Clock;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.locks.ReentrantLock;
import java.util.function.Supplier;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Soft-allocates stock to orders.
 *
 * <p>Checkout calls {@link #reserve} for every cart line when the customer clicks "Pay". The
 * reservation is {@link #commit committed} when the warehouse picks the order and
 * {@link #release released} when payment fails or the hold expires.
 *
 * <p>This class is called concurrently by all checkout worker threads. Every read-modify-write
 * of a SKU's stock record (and the matching reservation bookkeeping) runs under a lock owned by
 * that SKU only, so operations on one SKU are linearizable while different SKUs never wait for
 * each other.
 */
public class ReservationService {
    private final InventoryRepository repository;
    private final ReservationStore store;
    private final InventoryAuditLog audit;
    private final Clock clock;
    private final AtomicLong sequence = new AtomicLong();
    private final ConcurrentMap<String, ReentrantLock> skuLocks = new ConcurrentHashMap<>();

    public ReservationService(InventoryRepository repository, ReservationStore store, InventoryAuditLog audit, Clock clock) {
        this.repository = repository;
        this.store = store;
        this.audit = audit;
        this.clock = clock;
    }

    public ReservationService(InventoryRepository repository) {
        this(repository, new ReservationStore(), new InventoryAuditLog(), Clock.systemUTC());
    }

    /**
     * Reserves {@code quantity} units of {@code sku} for an order line.
     *
     * <p>Idempotent per (orderId, sku): a retry for an order line that already holds an active
     * reservation returns that reservation unchanged.
     *
     * @throws InsufficientStockException if fewer than {@code quantity} units are available
     * @throws UnknownSkuException if the SKU is not stocked
     */
    public Reservation reserve(String orderId, String sku, int quantity) {
        if (quantity <= 0) throw new IllegalArgumentException("quantity must be positive");
        return withSkuLock(sku, () -> reserveLocked(orderId, sku, quantity));
    }

    private Reservation reserveLocked(String orderId, String sku, int quantity) {
        Reservation existing = store.findActive(orderId, sku);
        if (existing != null) return existing;

        StockRecord record = repository.load(sku).orElseThrow(() -> new UnknownSkuException(sku));
        int available = record.available();
        if (available < quantity) {
            throw new InsufficientStockException(sku, quantity, available);
        }
        record.setReserved(record.getReserved() + quantity);
        Reservation reservation = new Reservation(nextId(), orderId, sku, quantity, clock.instant());
        audit.record(InventoryAuditLog.Action.RESERVE, sku, reservation.getId(), quantity, record.available(), clock.instant());
        repository.save(record);
        store.add(reservation);
        return reservation;
    }

    /**
     * Gives the reserved units back. Returns {@code true} if this call released the reservation,
     * {@code false} if it was not active any more (already released or committed).
     */
    public boolean release(String reservationId) {
        Reservation reservation = requireReservation(reservationId);
        return withSkuLock(reservation.getSku(), () -> releaseLocked(reservation));
    }

    private boolean releaseLocked(Reservation reservation) {
        String reservationId = reservation.getId();
        if (!reservation.isActive()) return false;
        StockRecord record = repository.load(reservation.getSku()).orElseThrow(() -> new UnknownSkuException(reservation.getSku()));
        record.setReserved(record.getReserved() - reservation.getQuantity());
        audit.record(InventoryAuditLog.Action.RELEASE, reservation.getSku(), reservationId, reservation.getQuantity(), record.available(), clock.instant());
        repository.save(record);
        reservation.setStatus(Reservation.Status.RELEASED);
        store.deactivate(reservation);
        return true;
    }

    /**
     * Converts the reservation into a shipment: the units leave on-hand stock. Returns
     * {@code false} if the reservation was not active any more.
     */
    public boolean commit(String reservationId) {
        Reservation reservation = requireReservation(reservationId);
        return withSkuLock(reservation.getSku(), () -> commitLocked(reservation));
    }

    private boolean commitLocked(Reservation reservation) {
        String reservationId = reservation.getId();
        if (!reservation.isActive()) return false;
        StockRecord record = repository.load(reservation.getSku()).orElseThrow(() -> new UnknownSkuException(reservation.getSku()));
        record.setReserved(record.getReserved() - reservation.getQuantity());
        record.setOnHand(record.getOnHand() - reservation.getQuantity());
        audit.record(InventoryAuditLog.Action.COMMIT, reservation.getSku(), reservationId, reservation.getQuantity(), record.available(), clock.instant());
        repository.save(record);
        reservation.setStatus(Reservation.Status.COMMITTED);
        store.deactivate(reservation);
        return true;
    }

    /** Goods receipt: adds units to on-hand stock. */
    public void restock(String sku, int quantity, String receiptRef) {
        if (quantity <= 0) throw new IllegalArgumentException("quantity must be positive");
        withSkuLock(sku, () -> {
            StockRecord record = repository.load(sku).orElseThrow(() -> new UnknownSkuException(sku));
            record.setOnHand(record.getOnHand() + quantity);
            audit.record(InventoryAuditLog.Action.RESTOCK, sku, receiptRef, quantity, record.available(), clock.instant());
            repository.save(record);
            return null;
        });
    }

    public int available(String sku) {
        return repository.load(sku).map(StockRecord::available).orElseThrow(() -> new UnknownSkuException(sku));
    }

    public List<Reservation> activeReservations(String sku) {
        return store.activeForSku(sku);
    }

    public Reservation get(String reservationId) {
        return store.get(reservationId);
    }

    private Reservation requireReservation(String reservationId) {
        Reservation r = store.get(reservationId);
        if (r == null) throw new IllegalArgumentException("unknown reservation " + reservationId);
        return r;
    }

    private <T> T withSkuLock(String sku, Supplier<T> action) {
        ReentrantLock lock = skuLocks.computeIfAbsent(sku, k -> new ReentrantLock());
        lock.lock();
        try {
            return action.get();
        } finally {
            lock.unlock();
        }
    }

    private String nextId() {
        return "RSV-" + sequence.incrementAndGet();
    }
}
