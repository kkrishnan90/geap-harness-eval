package com.northwind.commerce.pricing;

import static testkit.Assert.*;

import java.math.BigDecimal;
import testkit.Test;

public class PriceCalculatorTest {
    private final PriceCalculator calc = new PriceCalculator();

    @Test
    public void lineTotal() {
        assertAmount("59.97", calc.lineTotal(new BigDecimal("19.99"), 3), "line");
    }

    @Test
    public void includedVat() {
        assertAmount("20.00", calc.includedVat(new BigDecimal("120.00"), "standard"), "standard");
        assertAmount("0.48", calc.includedVat(new BigDecimal("10.00"), "reduced"), "reduced");
        assertAmount("0", calc.includedVat(new BigDecimal("10.00"), "zero"), "zero");
        assertThrows(IllegalArgumentException.class, () -> calc.includedVat(BigDecimal.ONE, "luxury"));
    }
}
