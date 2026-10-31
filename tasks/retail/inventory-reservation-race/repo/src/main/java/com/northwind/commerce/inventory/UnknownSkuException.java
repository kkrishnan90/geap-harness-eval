package com.northwind.commerce.inventory;

public class UnknownSkuException extends RuntimeException {
    public UnknownSkuException(String sku) {
        super("SKU not stocked: " + sku);
    }
}
