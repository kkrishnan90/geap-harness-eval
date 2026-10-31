package com.harborline.motor;

import static testkit.Assert.*;

import com.harborline.motor.rating.PremiumBreakdown;
import com.harborline.motor.rating.PremiumCalculator;
import com.harborline.motor.rating.RatingRequest;
import java.math.BigDecimal;
import java.util.List;
import testkit.Test;

/** Behaviour that is already correct and must stay so. */
public class PremiumRegressionGuardTest {
    private static BigDecimal d(String s) { return new BigDecimal(s); }

    @Test
    public void singleInstalmentIsGross() {
        assertEquals(List.of(d("436.41")), PremiumCalculator.split(d("436.41"), 1));
    }

    @Test
    public void evenSplitUnchanged() {
        assertEquals(List.of(d("25.00"), d("25.00"), d("25.00"), d("25.00")), PremiumCalculator.split(d("100.00"), 4));
    }

    @Test
    public void noFactorsKeepsBaseRate() {
        PremiumBreakdown b = new PremiumCalculator().calculate(
                new RatingRequest(d("389.65"), List.of(), d("150.00"), "GB", 1));
        assertAmount("389.65", b.netPremium(), "net");
        assertAmount("46.76", b.tax(), "tax");
    }
}
