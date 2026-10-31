package com.northwind.commerce.inventory;

import java.time.Instant;

/** A hold on stock for one order line. Status transitions: ACTIVE -> RELEASED | COMMITTED. */
public final class Reservation {
    public enum Status { ACTIVE, RELEASED, COMMITTED }

    private final String id;
    private final String orderId;
    private final String sku;
    private final int quantity;
    private final Instant createdAt;
    private volatile Status status = Status.ACTIVE;

    public Reservation(String id, String orderId, String sku, int quantity, Instant createdAt) {
        this.id = id;
        this.orderId = orderId;
        this.sku = sku;
        this.quantity = quantity;
        this.createdAt = createdAt;
    }

    public String getId() { return id; }

    public String getOrderId() { return orderId; }

    public String getSku() { return sku; }

    public int getQuantity() { return quantity; }

    public Instant getCreatedAt() { return createdAt; }

    public Status getStatus() { return status; }

    void setStatus(Status status) { this.status = status; }

    public boolean isActive() { return status == Status.ACTIVE; }

    @Override
    public String toString() {
        return "Reservation{" + id + " order=" + orderId + " " + sku + " x" + quantity + " " + status + "}";
    }
}
