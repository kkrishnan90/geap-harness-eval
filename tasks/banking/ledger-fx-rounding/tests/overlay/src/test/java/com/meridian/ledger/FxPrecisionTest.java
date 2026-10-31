package com.meridian.ledger;

import com.meridian.ledger.fx.FxConverter;
import com.meridian.ledger.fx.RateTable;
import com.meridian.ledger.money.Money;
import testkit.Test;

import java.math.BigDecimal;
import java.util.Currency;

import static testkit.Assert.*;

public class FxPrecisionTest {
    static final Currency EUR = Currency.getInstance("EUR"), USD = Currency.getInstance("USD"),
            JPY = Currency.getInstance("JPY");

    @Test
    public void tieOnDirectConversionUsesBankersRounding() {
        FxConverter c = new FxConverter(new RateTable().put("EUR", "USD", "1.0850"));
        assertEquals(Money.of("1.08", "USD"), c.convert(Money.of("1.00", "EUR"), USD));
    }

    @Test
    public void largeAmountsAreNotRoutedThroughDouble() {
        FxConverter c = new FxConverter(new RateTable().put("USD", "EUR", "1.5996").put("GBP", "EUR", "1.2325"));
        assertEquals(Money.of("10915850.36", "EUR"), c.convert(Money.of("6824112.50", "USD"), EUR));
        assertEquals(Money.of("2821653.46", "EUR"), c.convert(Money.of("2289374.00", "GBP"), EUR));
    }

    @Test
    public void reverseQuoteConversionIsExactDivision() {
        FxConverter c = new FxConverter(new RateTable().put("EUR", "USD", "1.0850").put("EUR", "JPY", "161.20"));
        assertEquals(Money.of("921658.99", "EUR"), c.convert(Money.of("1000000.00", "USD"), EUR));
        assertEquals(Money.of("6203.47", "EUR"), c.convert(Money.of("1000000", "JPY"), EUR));
        assertEquals(Money.of("2289.38", "EUR"), new FxConverter(new RateTable().put("EUR", "USD", "1.0920"))
                .convert(Money.of("2500.00", "USD"), EUR));
    }

    @Test
    public void derivedInverseRateKeepsPrecision() {
        BigDecimal inv = new RateTable().put("EUR", "USD", "1.0850").rate(USD, EUR);
        BigDecimal err = inv.multiply(new BigDecimal("1.0850")).subtract(BigDecimal.ONE).abs();
        assertTrue(err.compareTo(new BigDecimal("1E-20")) < 0, "inverse too imprecise: " + inv);
    }
}
