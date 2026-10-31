package com.northwind.commerce.inventory;

import static testkit.Assert.*;

import testkit.Test;

public class ReservationServiceTest {
    private InMemoryInventoryRepository repo;
    private ReservationService service;

    private void setUp() {
        repo = new InMemoryInventoryRepository()
            .put(StockRecord.of("TSHIRT-M-BLK", 10))
            .put(StockRecord.of("MUG-ESPRESSO", 2));
        service = new ReservationService(repo);
    }

    @Test
    public void reserveReducesAvailable() {
        setUp();
        Reservation r = service.reserve("ORD-1", "TSHIRT-M-BLK", 3);
        assertEquals(7, service.available("TSHIRT-M-BLK"));
        assertEquals(3, r.getQuantity());
        assertTrue(r.isActive());
        assertEquals(10, repo.load("TSHIRT-M-BLK").get().getOnHand());
    }

    @Test
    public void insufficientStockThrowsAndChangesNothing() {
        setUp();
        InsufficientStockException e = assertThrows(InsufficientStockException.class,
            () -> service.reserve("ORD-1", "MUG-ESPRESSO", 3));
        assertEquals(2, e.getAvailable());
        assertEquals(2, service.available("MUG-ESPRESSO"));
        assertEquals(0, service.activeReservations("MUG-ESPRESSO").size());
    }

    @Test
    public void reserveExactlyAvailable() {
        setUp();
        service.reserve("ORD-1", "MUG-ESPRESSO", 2);
        assertEquals(0, service.available("MUG-ESPRESSO"));
        assertThrows(InsufficientStockException.class, () -> service.reserve("ORD-2", "MUG-ESPRESSO", 1));
    }

    @Test
    public void retryForSameOrderLineIsIdempotent() {
        setUp();
        Reservation first = service.reserve("ORD-9", "TSHIRT-M-BLK", 2);
        Reservation again = service.reserve("ORD-9", "TSHIRT-M-BLK", 2);
        assertEquals(first.getId(), again.getId());
        assertEquals(8, service.available("TSHIRT-M-BLK"));
        assertEquals(1, service.activeReservations("TSHIRT-M-BLK").size());
    }

    @Test
    public void releaseReturnsStockOnce() {
        setUp();
        Reservation r = service.reserve("ORD-1", "TSHIRT-M-BLK", 4);
        assertTrue(service.release(r.getId()));
        assertFalse(service.release(r.getId()));
        assertEquals(10, service.available("TSHIRT-M-BLK"));
        assertEquals(Reservation.Status.RELEASED, service.get(r.getId()).getStatus());
    }

    @Test
    public void releasedOrderLineCanReserveAgain() {
        setUp();
        Reservation r = service.reserve("ORD-1", "TSHIRT-M-BLK", 4);
        service.release(r.getId());
        Reservation r2 = service.reserve("ORD-1", "TSHIRT-M-BLK", 1);
        assertFalse(r.getId().equals(r2.getId()), "a new reservation is created");
        assertEquals(9, service.available("TSHIRT-M-BLK"));
    }

    @Test
    public void commitShipsUnits() {
        setUp();
        Reservation r = service.reserve("ORD-1", "TSHIRT-M-BLK", 4);
        assertTrue(service.commit(r.getId()));
        StockRecord rec = repo.load("TSHIRT-M-BLK").get();
        assertEquals(6, rec.getOnHand());
        assertEquals(0, rec.getReserved());
        assertFalse(service.release(r.getId()), "committed reservation cannot be released");
    }

    @Test
    public void restockAddsOnHand() {
        setUp();
        service.reserve("ORD-1", "MUG-ESPRESSO", 2);
        service.restock("MUG-ESPRESSO", 5, "GRN-778");
        assertEquals(5, service.available("MUG-ESPRESSO"));
    }

    @Test
    public void unknownSkuAndBadQuantity() {
        setUp();
        assertThrows(UnknownSkuException.class, () -> service.reserve("ORD-1", "NOPE", 1));
        assertThrows(IllegalArgumentException.class, () -> service.reserve("ORD-1", "MUG-ESPRESSO", 0));
        assertThrows(IllegalArgumentException.class, () -> service.release("RSV-404"));
    }

    @Test
    public void auditTrailRecordsMovements() {
        InventoryAuditLog audit = new InventoryAuditLog();
        InMemoryInventoryRepository r = new InMemoryInventoryRepository().put(StockRecord.of("SKU-1", 5));
        ReservationService s = new ReservationService(r, new ReservationStore(), audit, java.time.Clock.systemUTC());
        Reservation res = s.reserve("O", "SKU-1", 2);
        s.release(res.getId());
        s.restock("SKU-1", 1, "GRN-1");
        assertEquals(1L, audit.count(InventoryAuditLog.Action.RESERVE));
        assertEquals(1L, audit.count(InventoryAuditLog.Action.RELEASE));
        assertEquals(1L, audit.count(InventoryAuditLog.Action.RESTOCK));
        assertTrue(audit.lines().get(0).contains("available_after=3"), audit.lines().get(0));
    }
}
