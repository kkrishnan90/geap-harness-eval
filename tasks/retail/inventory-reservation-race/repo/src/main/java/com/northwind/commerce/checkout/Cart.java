package com.northwind.commerce.checkout;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Customer basket. Adding the same SKU twice merges the lines. */
public class Cart {
    private final String orderId;
    private final Map<String, Integer> lines = new LinkedHashMap<>();

    public Cart(String orderId) {
        this.orderId = orderId;
    }

    public String getOrderId() { return orderId; }

    public Cart add(String sku, int quantity) {
        if (quantity <= 0) throw new IllegalArgumentException("quantity must be positive");
        lines.merge(sku, quantity, Integer::sum);
        return this;
    }

    public List<CartLine> lines() {
        List<CartLine> out = new ArrayList<>();
        lines.forEach((sku, q) -> out.add(new CartLine(sku, q)));
        return Collections.unmodifiableList(out);
    }

    public boolean isEmpty() { return lines.isEmpty(); }
}
