package com.northwind.commerce.checkout;

import static testkit.Assert.*;

import com.northwind.commerce.catalog.Catalog;
import com.northwind.commerce.catalog.Product;
import com.northwind.commerce.inventory.InMemoryInventoryRepository;
import com.northwind.commerce.inventory.ReservationService;
import com.northwind.commerce.inventory.StockRecord;
import com.northwind.commerce.pricing.PriceCalculator;
import java.math.BigDecimal;
import testkit.Test;

public class CheckoutServiceTest {
    private ReservationService reservations;
    private CheckoutService checkout;

    private void setUp() {
        Catalog catalog = new Catalog()
            .add(new Product("TSHIRT-M-BLK", "Organic tee M black", new BigDecimal("19.99"), "standard", true))
            .add(new Product("MUG-ESPRESSO", "Espresso mug", new BigDecimal("7.50"), "standard", true))
            .add(new Product("BOOK-OLD", "Discontinued book", new BigDecimal("12.00"), "zero", false));
        InMemoryInventoryRepository repo = new InMemoryInventoryRepository()
            .put(StockRecord.of("TSHIRT-M-BLK", 10))
            .put(StockRecord.of("MUG-ESPRESSO", 1))
            .put(StockRecord.of("BOOK-OLD", 4));
        reservations = new ReservationService(repo);
        checkout = new CheckoutService(catalog, reservations, new PriceCalculator());
    }

    @Test
    public void acceptsAndTotals() {
        setUp();
        CheckoutResult r = checkout.checkout(new Cart("ORD-1").add("TSHIRT-M-BLK", 2).add("MUG-ESPRESSO", 1));
        assertTrue(r.accepted());
        assertAmount("47.48", r.total(), "total");
        assertEquals(2, r.reservations().size());
        assertEquals(8, reservations.available("TSHIRT-M-BLK"));
    }

    @Test
    public void allOrNothing() {
        setUp();
        CheckoutResult r = checkout.checkout(new Cart("ORD-2").add("TSHIRT-M-BLK", 2).add("MUG-ESPRESSO", 2));
        assertFalse(r.accepted());
        assertEquals(10, reservations.available("TSHIRT-M-BLK"));
        assertEquals(1, reservations.available("MUG-ESPRESSO"));
    }

    @Test
    public void inactiveProductRejected() {
        setUp();
        CheckoutResult r = checkout.checkout(new Cart("ORD-3").add("BOOK-OLD", 1));
        assertFalse(r.accepted());
        assertEquals(4, reservations.available("BOOK-OLD"));
    }

    @Test
    public void emptyCartRejected() {
        setUp();
        assertFalse(checkout.checkout(new Cart("ORD-4")).accepted());
    }

    @Test
    public void mergesDuplicateLines() {
        setUp();
        CheckoutResult r = checkout.checkout(new Cart("ORD-5").add("TSHIRT-M-BLK", 1).add("TSHIRT-M-BLK", 2));
        assertTrue(r.accepted());
        assertEquals(7, reservations.available("TSHIRT-M-BLK"));
    }
}
