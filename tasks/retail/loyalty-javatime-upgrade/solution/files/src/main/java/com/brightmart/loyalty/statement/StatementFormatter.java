package com.brightmart.loyalty.statement;

import com.brightmart.loyalty.model.PointsEntry;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;

/** Formats the monthly e-statement lines. Called from the statement batch worker pool. */
public final class StatementFormatter {
    private static final DateTimeFormatter DATE = DateTimeFormatter.ISO_LOCAL_DATE;

    public String formatDate(Instant instant, ZoneId zone) {
        return DATE.format(instant.atZone(zone).toLocalDate());
    }

    /** {@code yyyy-MM-dd}, two spaces, signed points right-aligned in 6, two spaces, source. */
    public String formatLine(PointsEntry entry, ZoneId zone) {
        return String.format("%s  %+6d  %s", formatDate(entry.earnedAt(), zone), entry.points(), entry.source());
    }
}
