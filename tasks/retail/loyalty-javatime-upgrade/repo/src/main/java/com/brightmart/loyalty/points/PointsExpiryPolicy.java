package com.brightmart.loyalty.points;

import java.util.Calendar;
import java.util.Date;

/** Points are valid for 24 months. */
public final class PointsExpiryPolicy {
    public static final int VALIDITY_MONTHS = 24;

    public Date expiresAt(Date earnedAt) {
        Calendar cal = Calendar.getInstance();
        cal.setTime(earnedAt);
        cal.add(Calendar.MONTH, VALIDITY_MONTHS);
        return cal.getTime();
    }

    public boolean isExpired(Date earnedAt, Date now) {
        return !now.before(expiresAt(earnedAt));
    }
}
