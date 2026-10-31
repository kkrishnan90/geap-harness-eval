package com.northwind.commerce.inventory;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ConcurrentLinkedQueue;

/**
 * Append-only audit trail of stock movements, shipped to the data warehouse every 5 minutes.
 * Lines are formatted eagerly because the shipper is a dumb line forwarder.
 */
public class InventoryAuditLog {
    public enum Action { RESERVE, RELEASE, COMMIT, RESTOCK }

    private final ConcurrentLinkedQueue<String> lines = new ConcurrentLinkedQueue<>();

    public void record(Action action, String sku, String ref, int quantity, int availableAfter, Instant at) {
        lines.add(String.format(Locale.ROOT, "%s action=%s sku=%s ref=%s qty=%d available_after=%d",
            at, action, sku, ref, quantity, availableAfter));
    }

    public List<String> lines() {
        return new ArrayList<>(lines);
    }

    public long count(Action action) {
        String needle = " action=" + action + " ";
        return lines.stream().filter(l -> l.contains(needle)).count();
    }
}
