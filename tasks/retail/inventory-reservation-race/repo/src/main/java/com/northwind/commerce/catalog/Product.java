package com.northwind.commerce.catalog;

import java.math.BigDecimal;

public record Product(String sku, String title, BigDecimal listPrice, String taxClass, boolean active) {
    public Product {
        if (sku == null || sku.isBlank()) throw new IllegalArgumentException("sku required");
        if (listPrice == null || listPrice.signum() < 0) throw new IllegalArgumentException("bad price for " + sku);
    }
}
