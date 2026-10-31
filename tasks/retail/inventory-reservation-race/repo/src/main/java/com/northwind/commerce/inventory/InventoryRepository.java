package com.northwind.commerce.inventory;

import java.util.Collection;
import java.util.Optional;

/**
 * Storage port for stock records.
 *
 * <p>Implemented by {@link InMemoryInventoryRepository} (tests, local dev) and by the JDBC adapter
 * in {@code northwind-inventory-jdbc}, which is owned by the Fulfilment team. Do not change this
 * interface without a cross-team review.
 */
public interface InventoryRepository {

    /** Returns a detached copy of the record, or empty if the SKU is not stocked here. */
    Optional<StockRecord> load(String sku);

    /** Unconditionally stores the record (last write wins) and bumps its version. */
    void save(StockRecord record);

    /**
     * Stores the record only if the stored version still equals {@code expectedVersion}
     * (compare-and-set). On success the version is bumped and {@code true} is returned.
     */
    boolean saveIfVersion(StockRecord record, long expectedVersion);

    Collection<String> skus();
}
