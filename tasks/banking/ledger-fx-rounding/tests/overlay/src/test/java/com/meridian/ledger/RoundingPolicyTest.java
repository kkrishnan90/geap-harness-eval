package com.meridian.ledger;

import com.meridian.ledger.money.Money;
import com.meridian.ledger.money.Rounding;
import testkit.Test;

import java.math.RoundingMode;

import static testkit.Assert.*;

public class RoundingPolicyTest {
    static String r(String amount, String ccy) { return Money.of(amount, ccy).rounded().getAmount().toPlainString(); }

    @Test
    public void policyIsHalfEven() {
        assertEquals(RoundingMode.HALF_EVEN, Rounding.MODE);
    }

    @Test
    public void tiesGoToEvenCent() {
        assertEquals("2.34", r("2.345", "EUR"));
        assertEquals("2.36", r("2.355", "EUR"));
        assertEquals("0.12", r("0.125", "EUR"));
        assertEquals("-2.34", r("-2.345", "EUR"));
    }

    @Test
    public void tiesInZeroAndThreeDecimalCurrencies() {
        assertEquals("1234", r("1234.5", "JPY"));
        assertEquals("1236", r("1235.5", "JPY"));
        assertEquals("1.000", r("1.0005", "KWD"));
        assertEquals("1.002", r("1.0015", "KWD"));
    }
}
