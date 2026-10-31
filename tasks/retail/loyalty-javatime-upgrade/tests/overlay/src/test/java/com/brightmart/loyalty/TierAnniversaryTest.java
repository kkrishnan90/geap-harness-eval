package com.brightmart.loyalty;

import static testkit.Assert.*;

import com.brightmart.loyalty.tier.TierService;
import java.time.LocalDate;
import testkit.Test;

public class TierAnniversaryTest {
    private final TierService tiers = new TierService();

    private static LocalDate d(int y, int m, int day) { return LocalDate.of(y, m, day); }

    @Test
    public void anniversaryDayItselfCounts() {
        assertEquals(d(2026, 6, 10), tiers.nextAnniversary(d(2025, 6, 10), d(2026, 6, 10)));
        assertEquals(d(2027, 6, 10), tiers.nextAnniversary(d(2025, 6, 10), d(2026, 6, 11)));
    }

    @Test
    public void enrolmentDayIsNotAnAnniversary() {
        assertEquals(d(2026, 6, 10), tiers.nextAnniversary(d(2025, 6, 10), d(2025, 6, 10)));
        assertEquals(d(2026, 6, 10), tiers.nextAnniversary(d(2025, 6, 10), d(2025, 12, 31)));
    }

    @Test
    public void leapDayEnrolment() {
        LocalDate leap = d(2024, 2, 29);
        assertEquals(d(2025, 2, 28), tiers.nextAnniversary(leap, d(2025, 2, 28)));
        assertEquals(d(2026, 2, 28), tiers.nextAnniversary(leap, d(2025, 3, 1)));
        assertEquals(d(2028, 2, 29), tiers.nextAnniversary(leap, d(2027, 6, 1)));
        assertEquals(d(2028, 2, 29), tiers.nextAnniversary(leap, d(2028, 2, 29)));
    }

    @Test
    public void farFuture() {
        assertEquals(d(2040, 1, 31), tiers.nextAnniversary(d(2019, 1, 31), d(2040, 1, 31)));
        assertEquals(d(2041, 1, 31), tiers.nextAnniversary(d(2019, 1, 31), d(2040, 2, 1)));
    }
}
