package com.northwind.commerce.inventory;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

/** Thread-safe in-memory repository; each operation on a single key is atomic. */
public class InMemoryInventoryRepository implements InventoryRepository {
    private final ConcurrentMap<String, String> rows = new ConcurrentHashMap<>();

    public InMemoryInventoryRepository put(StockRecord record) {
        rows.put(record.getSku(), StockRecordCodec.encode(record));
        return this;
    }

    @Override
    public Optional<StockRecord> load(String sku) {
        String row = rows.get(sku);
        return row == null ? Optional.empty() : Optional.of(StockRecordCodec.decode(row));
    }

    @Override
    public void save(StockRecord record) {
        rows.compute(record.getSku(), (sku, current) -> {
            long next = current == null ? 1 : StockRecordCodec.decode(current).getVersion() + 1;
            StockRecord stored = record.copy();
            stored.setVersion(next);
            return StockRecordCodec.encode(stored);
        });
    }

    @Override
    public boolean saveIfVersion(StockRecord record, long expectedVersion) {
        boolean[] written = {false};
        rows.compute(record.getSku(), (sku, current) -> {
            long currentVersion = current == null ? 0 : StockRecordCodec.decode(current).getVersion();
            if (current != null && currentVersion != expectedVersion) return current;
            if (current == null && expectedVersion != 0) return null;
            StockRecord stored = record.copy();
            stored.setVersion(currentVersion + 1);
            written[0] = true;
            return StockRecordCodec.encode(stored);
        });
        return written[0];
    }

    @Override
    public Collection<String> skus() {
        return Collections.unmodifiableList(new ArrayList<>(rows.keySet()));
    }
}
