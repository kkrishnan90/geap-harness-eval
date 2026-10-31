package com.brightmart.loyalty.model;

import java.util.Date;
import java.util.Objects;

/** One line of a member's points ledger. Positive = earned, negative = redeemed. */
public final class PointsEntry {
    private final Date earnedAt;
    private final int points;
    private final String source;

    public PointsEntry(Date earnedAt, int points, String source) {
        this.earnedAt = new Date(Objects.requireNonNull(earnedAt, "earnedAt").getTime());
        this.points = points;
        this.source = Objects.requireNonNull(source, "source");
    }

    public Date earnedAt() { return new Date(earnedAt.getTime()); }
    public int points() { return points; }
    public String source() { return source; }
}
