package com.northwind.commerce.inventory;

import static testkit.Assert.*;

import testkit.Test;

public class InventoryRepositoryTest {
    @Test
    public void codecRoundTrip() {
        StockRecord r = new StockRecord("SKU-42", 17, 3, 9);
        StockRecord back = StockRecordCodec.decode(StockRecordCodec.encode(r));
        assertEquals("SKU-42", back.getSku());
        assertEquals(17, back.getOnHand());
        assertEquals(3, back.getReserved());
        assertEquals(9L, back.getVersion());
    }

    @Test
    public void codecRejectsCorruptRows() {
        assertThrows(IllegalArgumentException.class, () -> StockRecordCodec.decode("SKU|1|2"));
        assertThrows(IllegalArgumentException.class, () -> StockRecordCodec.decode("SKU|x|2|1"));
        assertThrows(IllegalArgumentException.class, () -> StockRecordCodec.encode(StockRecord.of("A|B", 1)));
    }

    @Test
    public void loadReturnsDetachedCopies() {
        InMemoryInventoryRepository repo = new InMemoryInventoryRepository().put(StockRecord.of("SKU-1", 5));
        StockRecord a = repo.load("SKU-1").get();
        a.setReserved(5);
        assertEquals(0, repo.load("SKU-1").get().getReserved());
        assertTrue(repo.load("missing").isEmpty());
    }

    @Test
    public void saveBumpsVersion() {
        InMemoryInventoryRepository repo = new InMemoryInventoryRepository().put(StockRecord.of("SKU-1", 5));
        StockRecord a = repo.load("SKU-1").get();
        repo.save(a);
        repo.save(a);
        assertEquals(2L, repo.load("SKU-1").get().getVersion());
    }

    @Test
    public void saveIfVersionIsCompareAndSet() {
        InMemoryInventoryRepository repo = new InMemoryInventoryRepository().put(StockRecord.of("SKU-1", 5));
        StockRecord a = repo.load("SKU-1").get();
        StockRecord b = repo.load("SKU-1").get();
        a.setReserved(1);
        b.setReserved(2);
        assertTrue(repo.saveIfVersion(a, a.getVersion()));
        assertFalse(repo.saveIfVersion(b, b.getVersion()), "stale version must be rejected");
        StockRecord now = repo.load("SKU-1").get();
        assertEquals(1, now.getReserved());
        assertEquals(1L, now.getVersion());
    }
}
