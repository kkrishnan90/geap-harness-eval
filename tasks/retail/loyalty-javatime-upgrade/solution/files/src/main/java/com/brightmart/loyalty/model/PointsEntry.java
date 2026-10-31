package com.brightmart.loyalty.model;

import java.time.Instant;
import java.util.Objects;

/** One line of a member's points ledger. Positive = earned, negative = redeemed. */
public final class PointsEntry {
    private final Instant earnedAt;
    private final int points;
    private final String source;

    public PointsEntry(Instant earnedAt, int points, String source) {
        this.earnedAt = Objects.requireNonNull(earnedAt, "earnedAt");
        this.points = points;
        this.source = Objects.requireNonNull(source, "source");
    }

    public Instant earnedAt() { return earnedAt; }
    public int points() { return points; }
    public String source() { return source; }
}
