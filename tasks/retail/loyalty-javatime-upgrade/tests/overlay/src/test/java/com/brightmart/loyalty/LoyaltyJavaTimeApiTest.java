package com.brightmart.loyalty;

import static testkit.Assert.*;

import com.brightmart.loyalty.model.Member;
import com.brightmart.loyalty.model.PointsEntry;
import com.brightmart.loyalty.points.PointsBalance;
import com.brightmart.loyalty.points.PointsExpiryPolicy;
import com.brightmart.loyalty.statement.StatementFormatter;
import com.brightmart.loyalty.tier.TierService;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.List;
import testkit.Test;

public class LoyaltyJavaTimeApiTest {
    private static final List<Class<?>> API = List.of(Member.class, PointsEntry.class, PointsExpiryPolicy.class,
            PointsBalance.class, TierService.class, StatementFormatter.class);
    private static final List<String> BANNED = List.of("java.util.Date", "java.util.Calendar", "java.util.TimeZone",
            "java.text.SimpleDateFormat", "java.text.DateFormat", "java.sql.Timestamp", "java.sql.Date");

    private static void check(String where, Class<?> type) {
        String n = type.isArray() ? type.getComponentType().getName() : type.getName();
        assertFalse(BANNED.contains(n), where + " still uses " + n);
    }

    @Test
    public void noLegacyDateTypesInPublicApi() {
        for (Class<?> c : API) {
            for (Method m : c.getDeclaredMethods()) {
                if (!Modifier.isPublic(m.getModifiers())) continue;
                check(c.getSimpleName() + "." + m.getName() + " return", m.getReturnType());
                for (Class<?> p : m.getParameterTypes()) check(c.getSimpleName() + "." + m.getName() + " param", p);
            }
            for (Constructor<?> k : c.getDeclaredConstructors()) {
                if (!Modifier.isPublic(k.getModifiers())) continue;
                for (Class<?> p : k.getParameterTypes()) check(c.getSimpleName() + " constructor param", p);
            }
        }
    }

    @Test
    public void memberCarriesHomeZone() {
        Member m = new Member("M-1001", LocalDate.of(2024, 2, 29), ZoneId.of("Asia/Tokyo"));
        assertEquals(LocalDate.of(2024, 2, 29), m.enrolledOn());
        assertEquals(ZoneId.of("Asia/Tokyo"), m.homeZone());
        assertEquals("M-1001", m.memberId());
    }

    @Test
    public void entryIsInstantBased() {
        Instant t = Instant.parse("2026-03-15T09:30:00Z");
        PointsEntry e = new PointsEntry(t, 120, "STORE");
        assertEquals(t, e.earnedAt());
        assertEquals(120, e.points());
    }
}
