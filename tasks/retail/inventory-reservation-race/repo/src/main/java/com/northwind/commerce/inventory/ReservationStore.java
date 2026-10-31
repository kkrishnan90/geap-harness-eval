package com.northwind.commerce.inventory;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Index of reservations by id and by (order, sku). */
public class ReservationStore {
    private final Map<String, Reservation> byId = new HashMap<>();
    private final Map<String, Reservation> activeByOrderLine = new HashMap<>();

    private static String key(String orderId, String sku) {
        return orderId + "#" + sku;
    }

    public void add(Reservation r) {
        byId.put(r.getId(), r);
        activeByOrderLine.put(key(r.getOrderId(), r.getSku()), r);
    }

    public Reservation get(String reservationId) {
        return byId.get(reservationId);
    }

    /** Active reservation for an order line, or null. */
    public Reservation findActive(String orderId, String sku) {
        Reservation r = activeByOrderLine.get(key(orderId, sku));
        return r != null && r.isActive() ? r : null;
    }

    /** Called after a reservation left the ACTIVE state. */
    public void deactivate(Reservation r) {
        activeByOrderLine.remove(key(r.getOrderId(), r.getSku()), r);
    }

    public List<Reservation> activeForSku(String sku) {
        List<Reservation> out = new ArrayList<>();
        for (Reservation r : byId.values()) {
            if (r.isActive() && r.getSku().equals(sku)) out.add(r);
        }
        return out;
    }

    public int size() {
        return byId.size();
    }
}
