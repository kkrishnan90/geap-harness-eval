package com.meridian.ledger;

import com.meridian.ledger.fx.FxConverter;
import com.meridian.ledger.fx.RateNotFoundException;
import com.meridian.ledger.fx.RateTable;
import com.meridian.ledger.money.Money;
import testkit.Test;

import java.util.Currency;

import static testkit.Assert.*;

public class FxTest {
    static final Currency EUR = Currency.getInstance("EUR"), USD = Currency.getInstance("USD"),
            GBP = Currency.getInstance("GBP"), CHF = Currency.getInstance("CHF");

    static RateTable rates() {
        return new RateTable().put("EUR", "USD", "1.0850").put("GBP", "EUR", "1.1650").put("EUR", "JPY", "161.20");
    }

    @Test
    public void directRate() {
        assertAmount("1.0850", rates().rate(EUR, USD), "EUR/USD");
        assertAmount("1", rates().rate(EUR, EUR), "same currency");
    }

    @Test
    public void missingRate() {
        assertThrows(RateNotFoundException.class, () -> rates().rate(EUR, CHF));
    }

    @Test
    public void overlayReplacesQuotes() {
        RateTable t = rates().overlay(new RateTable().put("EUR", "USD", "1.0700"));
        assertAmount("1.0700", t.rate(EUR, USD), "overlaid");
        assertAmount("1.1650", t.rate(GBP, EUR), "kept");
    }

    @Test
    public void convertWithDirectQuote() {
        FxConverter c = new FxConverter(rates());
        assertEquals(Money.of("291.25", "EUR"), c.convert(Money.of("250.00", "GBP"), EUR));
        assertEquals(Money.of("108.50", "USD"), c.convert(Money.of("100.00", "EUR"), USD));
        assertEquals(Money.of("16120", "JPY"), c.convert(Money.of("100.00", "EUR"), Currency.getInstance("JPY")));
    }

    @Test
    public void convertSameCurrencyRounds() {
        assertEquals(Money.of("10.13", "EUR"), new FxConverter(rates()).convert(Money.of("10.126", "EUR"), EUR));
    }
}
