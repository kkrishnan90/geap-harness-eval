package com.brightmart.loyalty.tier;

import java.time.LocalDate;

/** Tier thresholds and the membership anniversary on which tiers are re-assessed. */
public final class TierService {

    public Tier tierFor(int qualifyingPoints) {
        if (qualifyingPoints >= 20_000) return Tier.PLATINUM;
        if (qualifyingPoints >= 7_500) return Tier.GOLD;
        if (qualifyingPoints >= 2_500) return Tier.SILVER;
        return Tier.BRONZE;
    }

    /**
     * Next tier re-assessment date: the first anniversary of {@code enrolledOn} (year 1, 2, ...)
     * that is on or after {@code today}. A 29 February enrolment has its anniversary on
     * 28 February in non-leap years.
     */
    public LocalDate nextAnniversary(LocalDate enrolledOn, LocalDate today) {
        int years = Math.max(1, today.getYear() - enrolledOn.getYear());
        LocalDate candidate = enrolledOn.plusYears(years);
        while (candidate.isBefore(today)) {
            years++;
            candidate = enrolledOn.plusYears(years);
        }
        return candidate;
    }
}
