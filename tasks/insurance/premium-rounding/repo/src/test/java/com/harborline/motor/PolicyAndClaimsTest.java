package com.harborline.motor;

import static testkit.Assert.*;

import com.harborline.motor.claims.ExcessCalculator;
import com.harborline.motor.policy.Policy;
import com.harborline.motor.policy.PolicyNumberGenerator;
import java.math.BigDecimal;
import java.time.LocalDate;
import testkit.Test;

public class PolicyAndClaimsTest {
    @Test
    public void policyNumbersCarryLuhnDigit() {
        PolicyNumberGenerator gen = new PolicyNumberGenerator(1234);
        String n = gen.next();
        assertEquals(11, n.length());
        assertTrue(PolicyNumberGenerator.isValid(n), n);
        assertFalse(PolicyNumberGenerator.isValid(n.substring(0, 10) + ((n.charAt(10) - '0' + 1) % 10)));
    }

    @Test
    public void inForceWindowIsHalfOpen() {
        Policy p = new Policy("HM000012343", "AB12CDE", Policy.Cover.COMPREHENSIVE,
                LocalDate.of(2026, 3, 1), LocalDate.of(2027, 3, 1));
        assertTrue(p.isInForce(LocalDate.of(2026, 3, 1)));
        assertFalse(p.isInForce(LocalDate.of(2027, 3, 1)));
    }

    @Test
    public void youngDriverExcess() {
        ExcessCalculator ex = new ExcessCalculator();
        assertAmount("600.00", ex.totalExcess(new BigDecimal("250"), new BigDecimal("100"), 22, false), "excess");
        assertAmount("75.00", ex.totalExcess(new BigDecimal("250"), new BigDecimal("100"), 22, true), "windscreen");
        assertAmount("0.00", ex.settlement(new BigDecimal("50"), new BigDecimal("75")), "settlement");
    }
}
