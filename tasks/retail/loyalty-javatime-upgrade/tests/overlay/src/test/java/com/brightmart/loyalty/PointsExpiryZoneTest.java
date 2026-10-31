package com.brightmart.loyalty;

import static testkit.Assert.*;

import com.brightmart.loyalty.model.PointsEntry;
import com.brightmart.loyalty.points.PointsBalance;
import com.brightmart.loyalty.points.PointsExpiryPolicy;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;
import testkit.Test;

public class PointsExpiryZoneTest {
    private static final ZoneId TOKYO = ZoneId.of("Asia/Tokyo");
    private static final ZoneId LONDON = ZoneId.of("Europe/London");
    private static final ZoneId SYDNEY = ZoneId.of("Australia/Sydney");
    private final PointsExpiryPolicy policy = new PointsExpiryPolicy();

    private static Instant local(String dateTime, ZoneId zone) {
        return LocalDateTime.parse(dateTime).atZone(zone).toInstant();
    }

    @Test
    public void expiresAtEndOfMonthTwoYearsLater() {
        assertEquals(LocalDate.of(2026, 3, 31), policy.expiryDate(local("2024-03-15T10:00", LONDON), LONDON));
        assertEquals(LocalDate.of(2026, 3, 31), policy.expiryDate(local("2024-03-01T00:00", LONDON), LONDON));
        assertEquals(LocalDate.of(2026, 2, 28), policy.expiryDate(local("2024-02-29T12:00", LONDON), LONDON));
    }

    @Test
    public void earnMonthIsTakenInMemberZone() {
        Instant t = Instant.parse("2024-03-31T16:00:00Z"); // 1 April 01:00 in Tokyo, 31 March 17:00 in London
        assertEquals(LocalDate.of(2026, 4, 30), policy.expiryDate(t, TOKYO));
        assertEquals(LocalDate.of(2026, 3, 31), policy.expiryDate(t, LONDON));
    }

    @Test
    public void usableThroughLastLocalDay() {
        Instant earned = local("2024-04-10T09:00", TOKYO);
        assertFalse(policy.isExpired(earned, local("2026-04-30T23:59:59", TOKYO), TOKYO));
        assertTrue(policy.isExpired(earned, local("2026-05-01T00:00", TOKYO), TOKYO));
    }

    @Test
    public void sydneyMidnightAcrossUtcDate() {
        Instant earned = local("2024-06-01T00:15", SYDNEY); // still 31 May in UTC
        assertEquals(LocalDate.of(2026, 6, 30), policy.expiryDate(earned, SYDNEY));
        assertFalse(policy.isExpired(earned, Instant.parse("2026-06-30T13:00:00Z"), SYDNEY)); // 23:00 local
        assertTrue(policy.isExpired(earned, Instant.parse("2026-06-30T14:00:00Z"), SYDNEY)); // 1 July 00:00 local
    }

    @Test
    public void balanceUsesZoneAwareExpiry() {
        PointsBalance b = new PointsBalance(policy);
        List<PointsEntry> ledger = List.of(
                new PointsEntry(local("2024-04-01T08:30", TOKYO), 500, "STORE"),
                new PointsEntry(local("2025-01-10T12:00", TOKYO), 200, "STORE"),
                new PointsEntry(local("2025-02-01T12:00", TOKYO), -150, "REDEEM"));
        assertEquals(550, b.available(ledger, local("2026-04-30T22:00", TOKYO), TOKYO));
        assertEquals(50, b.available(ledger, local("2026-05-01T07:00", TOKYO), TOKYO));
        assertEquals(0, b.available(List.of(new PointsEntry(local("2026-01-01T10:00", TOKYO), -10, "REDEEM")),
                local("2026-01-02T10:00", TOKYO), TOKYO));
    }
}
