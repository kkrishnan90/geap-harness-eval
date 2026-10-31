package com.harborline.motor;

import static testkit.Assert.*;

import com.harborline.motor.rating.PremiumBreakdown;
import com.harborline.motor.rating.PremiumCalculator;
import com.harborline.motor.rating.RatingRequest;
import java.math.BigDecimal;
import java.util.List;
import testkit.Test;

public class PremiumCalculatorTest {
    private static BigDecimal d(String s) { return new BigDecimal(s); }

    private final PremiumCalculator calc = new PremiumCalculator();

    @Test
    public void standardQuote() {
        PremiumBreakdown b = calc.calculate(new RatingRequest(d("500.00"), List.of(d("1.2"), d("0.9")), d("150.00"), "GB", 4));
        assertAmount("540.00", b.netPremium(), "net");
        assertAmount("64.80", b.tax(), "tax");
        assertAmount("604.80", b.grossPremium(), "gross");
        assertEquals(4, b.instalments().size());
        for (BigDecimal i : b.instalments()) assertAmount("151.20", i, "instalment");
    }

    @Test
    public void jerseyHasNoTax() {
        PremiumBreakdown b = calc.calculate(new RatingRequest(d("420.00"), List.of(d("1.25")), d("150.00"), "GB-JSY", 1));
        assertAmount("525.00", b.netPremium(), "net");
        assertAmount("0.00", b.tax(), "tax");
        assertEquals(List.of(d("525.00")), b.instalments());
    }

    @Test
    public void scaleIsPence() {
        PremiumBreakdown b = calc.calculate(new RatingRequest(d("300"), List.of(d("1.1")), d("150.00"), "IE", 2));
        assertEquals(2, b.netPremium().scale());
        assertEquals(2, b.tax().scale());
        assertEquals(2, b.grossPremium().scale());
    }

    @Test
    public void unknownRegionRejected() {
        assertThrows(IllegalArgumentException.class,
                () -> calc.calculate(new RatingRequest(d("300"), List.of(), d("150.00"), "FR", 1)));
    }

    @Test
    public void instalmentRangeChecked() {
        assertThrows(IllegalArgumentException.class, () -> new RatingRequest(d("300"), List.of(), d("1"), "GB", 13));
        assertThrows(IllegalArgumentException.class, () -> new RatingRequest(d("300"), List.of(), d("1"), "GB", 0));
    }
}
