package com.meridian.ledger.money;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Currency;

/** Group accounting policy for rounding monetary amounts to a currency's minor unit. */
public final class Rounding {
    private Rounding() {}

    /** Rounding mode applied whenever an amount is brought to its currency's minor unit. */
    public static final RoundingMode MODE = RoundingMode.HALF_EVEN;

    public static int minorUnits(Currency currency) {
        int d = currency.getDefaultFractionDigits();
        return d < 0 ? 0 : d;
    }

    public static BigDecimal round(BigDecimal amount, Currency currency) {
        return amount.setScale(minorUnits(currency), MODE);
    }
}
