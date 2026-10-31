package com.northwind.commerce.inventory;

/**
 * Stock position of one SKU in one fulfilment node.
 *
 * <p>Instances are plain value holders: the repository hands out copies, so mutating a record
 * has no effect until it is saved back.
 */
public final class StockRecord {
    private final String sku;
    private int onHand;
    private int reserved;
    private long version;

    public StockRecord(String sku, int onHand, int reserved, long version) {
        if (sku == null || sku.isBlank()) throw new IllegalArgumentException("sku required");
        if (onHand < 0 || reserved < 0) throw new IllegalArgumentException("negative stock for " + sku);
        this.sku = sku;
        this.onHand = onHand;
        this.reserved = reserved;
        this.version = version;
    }

    public static StockRecord of(String sku, int onHand) {
        return new StockRecord(sku, onHand, 0, 0L);
    }

    public String getSku() { return sku; }

    public int getOnHand() { return onHand; }

    public int getReserved() { return reserved; }

    /** Optimistic-locking version maintained by the repository. */
    public long getVersion() { return version; }

    /** Units that can still be promised to new orders. */
    public int available() { return onHand - reserved; }

    public void setOnHand(int onHand) { this.onHand = onHand; }

    public void setReserved(int reserved) { this.reserved = reserved; }

    void setVersion(long version) { this.version = version; }

    public StockRecord copy() { return new StockRecord(sku, onHand, reserved, version); }

    @Override
    public String toString() {
        return "StockRecord{" + sku + " onHand=" + onHand + " reserved=" + reserved + " v" + version + "}";
    }
}
