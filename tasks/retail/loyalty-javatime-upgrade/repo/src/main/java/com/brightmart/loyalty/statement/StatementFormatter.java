package com.brightmart.loyalty.statement;

import com.brightmart.loyalty.model.PointsEntry;
import java.text.SimpleDateFormat;
import java.util.Date;

/** Formats the monthly e-statement lines. Called from the statement batch worker pool. */
public final class StatementFormatter {
    private static final SimpleDateFormat DATE = new SimpleDateFormat("yyyy-MM-dd");

    public String formatDate(Date date) {
        return DATE.format(date);
    }

    /** {@code yyyy-MM-dd}, two spaces, signed points right-aligned in 6, two spaces, source. */
    public String formatLine(PointsEntry entry) {
        return String.format("%s  %+6d  %s", formatDate(entry.earnedAt()), entry.points(), entry.source());
    }
}
