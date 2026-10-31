package com.meridian.ledger.fx;

import com.meridian.ledger.money.Money;
import com.meridian.ledger.money.Rounding;

import java.math.BigDecimal;
import java.util.Currency;

/** Converts amounts with a rate table and rounds the result to the target's minor unit. */
public final class FxConverter {
    private final RateTable rates;

    public FxConverter(RateTable rates) { this.rates = rates; }

    public RateTable getRates() { return rates; }

    public Money convert(Money money, Currency target) {
        if (money.getCurrency().equals(target)) return money.rounded();
        BigDecimal rate = rates.rate(money.getCurrency(), target);
        double converted = money.getAmount().doubleValue() * rate.doubleValue();
        return Money.of(Rounding.round(BigDecimal.valueOf(converted), target), target);
    }
}
