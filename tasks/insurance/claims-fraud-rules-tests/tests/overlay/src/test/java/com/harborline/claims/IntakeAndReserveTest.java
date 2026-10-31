package com.harborline.claims;

import static testkit.Assert.*;

import com.harborline.claims.intake.ClaimNumberFormat;
import com.harborline.claims.reserve.ReserveCalculator;
import java.math.BigDecimal;
import java.time.LocalDate;
import testkit.Test;

public class IntakeAndReserveTest {
    @Test
    public void claimNumbers() {
        assertEquals("CL-2026-000042", ClaimNumberFormat.format(LocalDate.of(2026, 5, 1), 42));
        assertTrue(ClaimNumberFormat.isValid("CL-2026-000042"));
        assertFalse(ClaimNumberFormat.isValid("CL-2026-000000"));
    }

    @Test
    public void reserveRoundsUpToPounds() {
        assertAmount("1150.00", new ReserveCalculator().initialReserve(ReserveCalculator.Line.MOTOR, new BigDecimal("1000")), "motor");
        assertAmount("126.00", new ReserveCalculator().initialReserve(ReserveCalculator.Line.HOME, new BigDecimal("100.01")), "home");
    }
}
