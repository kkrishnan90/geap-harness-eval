package com.northwind.commerce.checkout;

public record CartLine(String sku, int quantity) {
    public CartLine {
        if (quantity <= 0) throw new IllegalArgumentException("quantity must be positive");
    }
}
