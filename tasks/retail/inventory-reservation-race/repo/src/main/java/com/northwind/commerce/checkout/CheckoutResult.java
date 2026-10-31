package com.northwind.commerce.checkout;

import com.northwind.commerce.inventory.Reservation;
import java.math.BigDecimal;
import java.util.List;

public record CheckoutResult(boolean accepted, List<Reservation> reservations, BigDecimal total, String rejectionReason) {
    public static CheckoutResult accepted(List<Reservation> reservations, BigDecimal total) {
        return new CheckoutResult(true, List.copyOf(reservations), total, null);
    }

    public static CheckoutResult rejected(String reason) {
        return new CheckoutResult(false, List.of(), BigDecimal.ZERO, reason);
    }
}
