package com.meridian.ledger.fx;

import java.math.BigDecimal;
import java.util.Currency;
import java.util.Objects;

/** A market quote: 1 unit of {@code base} = {@code rate} units of {@code quote} (e.g. EUR/USD 1.0850). */
public final class FxRate {
    private final Currency base;
    private final Currency quote;
    private final BigDecimal rate;

    public FxRate(Currency base, Currency quote, BigDecimal rate) {
        this.base = Objects.requireNonNull(base);
        this.quote = Objects.requireNonNull(quote);
        this.rate = Objects.requireNonNull(rate);
        if (rate.signum() <= 0) throw new IllegalArgumentException("rate must be positive: " + rate);
        if (base.equals(quote)) throw new IllegalArgumentException("base == quote: " + base);
    }

    public static FxRate of(String base, String quote, String rate) {
        return new FxRate(Currency.getInstance(base), Currency.getInstance(quote), new BigDecimal(rate));
    }

    public Currency getBase() { return base; }
    public Currency getQuote() { return quote; }
    public BigDecimal getRate() { return rate; }

    @Override
    public String toString() { return base + "/" + quote + " " + rate.toPlainString(); }
}
