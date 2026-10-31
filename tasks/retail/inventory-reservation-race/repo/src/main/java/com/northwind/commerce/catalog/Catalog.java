package com.northwind.commerce.catalog;

import java.util.Collection;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/** Read-mostly product catalogue, refreshed from PIM nightly. */
public class Catalog {
    private final Map<String, Product> products = new ConcurrentHashMap<>();

    public Catalog add(Product p) {
        products.put(p.sku(), p);
        return this;
    }

    public Optional<Product> find(String sku) {
        return Optional.ofNullable(products.get(sku));
    }

    public Product require(String sku) {
        Product p = products.get(sku);
        if (p == null || !p.active()) throw new IllegalArgumentException("product not sellable: " + sku);
        return p;
    }

    public Collection<Product> all() {
        return products.values();
    }
}
