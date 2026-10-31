package com.brightmart.loyalty.tier;

import java.util.Calendar;
import java.util.Date;

/** Tier thresholds and the membership anniversary on which tiers are re-assessed. */
public final class TierService {

    public Tier tierFor(int qualifyingPoints) {
        if (qualifyingPoints >= 20_000) return Tier.PLATINUM;
        if (qualifyingPoints >= 7_500) return Tier.GOLD;
        if (qualifyingPoints >= 2_500) return Tier.SILVER;
        return Tier.BRONZE;
    }

    /** Next tier re-assessment date: the membership anniversary after {@code now}. */
    public Date nextAnniversary(Date enrolledAt, Date now) {
        Calendar cal = Calendar.getInstance();
        cal.setTime(enrolledAt);
        while (!cal.getTime().after(now)) {
            cal.add(Calendar.YEAR, 1);
        }
        return cal.getTime();
    }
}
