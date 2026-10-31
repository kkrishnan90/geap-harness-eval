package com.meridian.ledger.fx;

import com.meridian.ledger.money.Money;
import com.meridian.ledger.money.Rounding;

import java.math.BigDecimal;
import java.math.MathContext;
import java.util.Currency;

/** Converts amounts with a rate table and rounds the result to the target's minor unit. */
public final class FxConverter {
    private final RateTable rates;

    public FxConverter(RateTable rates) { this.rates = rates; }

    public RateTable getRates() { return rates; }

    public Money convert(Money money, Currency target) {
        if (money.getCurrency().equals(target)) return money.rounded();
        Currency from = money.getCurrency();
        BigDecimal converted;
        if (rates.hasDirect(from, target)) {
            converted = money.getAmount().multiply(rates.rate(from, target));
        } else if (rates.hasDirect(target, from)) {
            converted = money.getAmount().divide(rates.rate(target, from), MathContext.DECIMAL128);
        } else {
            converted = money.getAmount().multiply(rates.rate(from, target));
        }
        return Money.of(Rounding.round(converted, target), target);
    }
}
