package com.northwind.commerce.checkout;

import com.northwind.commerce.catalog.Catalog;
import com.northwind.commerce.catalog.Product;
import com.northwind.commerce.inventory.InsufficientStockException;
import com.northwind.commerce.inventory.Reservation;
import com.northwind.commerce.inventory.ReservationService;
import com.northwind.commerce.pricing.PriceCalculator;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

/**
 * Places the stock holds for a cart. All-or-nothing: if any line cannot be reserved, the lines
 * already reserved are released again and the checkout is rejected.
 */
public class CheckoutService {
    private final Catalog catalog;
    private final ReservationService reservations;
    private final PriceCalculator prices;

    public CheckoutService(Catalog catalog, ReservationService reservations, PriceCalculator prices) {
        this.catalog = catalog;
        this.reservations = reservations;
        this.prices = prices;
    }

    public CheckoutResult checkout(Cart cart) {
        if (cart.isEmpty()) return CheckoutResult.rejected("empty cart");
        List<Reservation> held = new ArrayList<>();
        BigDecimal total = BigDecimal.ZERO;
        try {
            for (CartLine line : cart.lines()) {
                Product product = catalog.require(line.sku());
                held.add(reservations.reserve(cart.getOrderId(), line.sku(), line.quantity()));
                total = total.add(prices.lineTotal(product.listPrice(), line.quantity()));
            }
        } catch (InsufficientStockException | IllegalArgumentException e) {
            for (Reservation r : held) reservations.release(r.getId());
            return CheckoutResult.rejected(e.getMessage());
        }
        return CheckoutResult.accepted(held, total);
    }
}
