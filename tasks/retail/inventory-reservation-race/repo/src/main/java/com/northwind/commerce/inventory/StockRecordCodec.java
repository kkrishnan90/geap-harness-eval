package com.northwind.commerce.inventory;

/**
 * Wire format used by the stock cache ({@code sku|onHand|reserved|version}). The in-memory
 * repository stores encoded strings so that it behaves like the Redis-backed production cache:
 * every load returns a fresh, detached object.
 */
public final class StockRecordCodec {
    private static final char SEP = '|';

    private StockRecordCodec() {}

    public static String encode(StockRecord r) {
        if (r.getSku().indexOf(SEP) >= 0) throw new IllegalArgumentException("sku contains separator: " + r.getSku());
        return new StringBuilder(r.getSku().length() + 24)
            .append(r.getSku()).append(SEP)
            .append(r.getOnHand()).append(SEP)
            .append(r.getReserved()).append(SEP)
            .append(r.getVersion())
            .toString();
    }

    public static StockRecord decode(String s) {
        String[] parts = s.split("\\|", -1);
        if (parts.length != 4) throw new IllegalArgumentException("corrupt stock record: " + s);
        try {
            return new StockRecord(parts[0], Integer.parseInt(parts[1]), Integer.parseInt(parts[2]), Long.parseLong(parts[3]));
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("corrupt stock record: " + s, e);
        }
    }
}
