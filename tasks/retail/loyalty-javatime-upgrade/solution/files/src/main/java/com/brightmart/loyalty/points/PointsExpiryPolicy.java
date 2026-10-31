package com.brightmart.loyalty.points;

import java.time.Instant;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneId;

/**
 * Points are valid until the end of the month 24 months after the (local) month they
 * were earned in: points earned any day in March 2024 can be used up to and including
 * 31 March 2026.
 */
public final class PointsExpiryPolicy {
    public static final int VALIDITY_MONTHS = 24;

    /** Last local date on which the points can still be used. */
    public LocalDate expiryDate(Instant earnedAt, ZoneId zone) {
        LocalDate earned = earnedAt.atZone(zone).toLocalDate();
        return YearMonth.from(earned).plusMonths(VALIDITY_MONTHS).atEndOfMonth();
    }

    public boolean isExpired(Instant earnedAt, Instant now, ZoneId zone) {
        return now.atZone(zone).toLocalDate().isAfter(expiryDate(earnedAt, zone));
    }
}
