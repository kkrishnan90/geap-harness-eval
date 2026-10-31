package com.meridian.ledger;

import com.meridian.ledger.money.CurrencyMismatchException;
import com.meridian.ledger.money.Money;
import testkit.Test;

import static testkit.Assert.*;

public class MoneyTest {
    @Test
    public void arithmeticIsExact() {
        Money a = Money.of("0.10", "EUR"), b = Money.of("0.20", "EUR");
        assertEquals(Money.of("0.30", "EUR"), a.add(b));
        assertEquals(Money.of("-0.10", "EUR"), a.subtract(b));
        assertEquals(Money.of("-0.10", "EUR"), a.negate());
    }

    @Test
    public void equalityIgnoresScale() {
        assertEquals(Money.of("1.5", "USD"), Money.of("1.50", "USD"));
        assertEquals(Money.of("1.5", "USD").hashCode(), Money.of("1.50", "USD").hashCode());
        assertFalse(Money.of("1.50", "USD").equals(Money.of("1.50", "EUR")));
    }

    @Test
    public void currencyMismatch() {
        assertThrows(CurrencyMismatchException.class, () -> Money.of("1", "EUR").add(Money.of("1", "USD")));
    }

    @Test
    public void roundsToMinorUnit() {
        assertEquals("2.35", Money.of("2.346", "EUR").rounded().getAmount().toPlainString());
        assertEquals("1235", Money.of("1234.7", "JPY").rounded().getAmount().toPlainString());
        assertEquals("1.234", Money.of("1.2341", "KWD").rounded().getAmount().toPlainString());
    }

    @Test
    public void zeroHasMinorUnitScale() {
        assertEquals("0.00", Money.zero(java.util.Currency.getInstance("EUR")).getAmount().toPlainString());
        assertEquals("0", Money.zero(java.util.Currency.getInstance("JPY")).getAmount().toPlainString());
    }
}
