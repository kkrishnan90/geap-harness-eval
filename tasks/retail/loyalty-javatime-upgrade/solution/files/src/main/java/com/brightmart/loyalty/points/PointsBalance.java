package com.brightmart.loyalty.points;

import com.brightmart.loyalty.model.PointsEntry;
import java.time.Instant;
import java.time.ZoneId;
import java.util.List;

/** Spendable balance: unexpired earned points minus redemptions, never below zero. */
public final class PointsBalance {
    private final PointsExpiryPolicy expiry;

    public PointsBalance(PointsExpiryPolicy expiry) { this.expiry = expiry; }

    public int available(List<PointsEntry> entries, Instant now, ZoneId zone) {
        int total = 0;
        for (PointsEntry e : entries) {
            if (e.points() < 0) {
                total += e.points();
            } else if (!expiry.isExpired(e.earnedAt(), now, zone)) {
                total += e.points();
            }
        }
        return Math.max(0, total);
    }
}
