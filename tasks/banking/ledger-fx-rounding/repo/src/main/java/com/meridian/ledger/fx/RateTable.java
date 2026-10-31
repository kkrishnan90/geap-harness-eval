package com.meridian.ledger.fx;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Currency;
import java.util.HashMap;
import java.util.Map;

/**
 * Set of quotes valid for one booking or closing date. Treasury publishes each pair once,
 * in market convention (EUR/USD, GBP/EUR, ...); the reverse direction is derived.
 */
public final class RateTable {
    private final Map<String, FxRate> quotes = new HashMap<>();

    private static String key(Currency from, Currency to) { return from.getCurrencyCode() + to.getCurrencyCode(); }

    public RateTable put(FxRate rate) {
        quotes.put(key(rate.getBase(), rate.getQuote()), rate);
        return this;
    }

    public RateTable put(String base, String quote, String rate) { return put(FxRate.of(base, quote, rate)); }

    public boolean hasDirect(Currency from, Currency to) { return quotes.containsKey(key(from, to)); }

    /** Units of {@code to} per 1 unit of {@code from}. */
    public BigDecimal rate(Currency from, Currency to) {
        if (from.equals(to)) return BigDecimal.ONE;
        FxRate direct = quotes.get(key(from, to));
        if (direct != null) return direct.getRate();
        FxRate reverse = quotes.get(key(to, from));
        if (reverse != null) {
            return BigDecimal.valueOf(1.0 / reverse.getRate().doubleValue()).setScale(6, RoundingMode.HALF_UP);
        }
        throw new RateNotFoundException("no rate " + from + "->" + to);
    }

    /** A copy of this table with all quotes replaced by those of {@code other} where present. */
    public RateTable overlay(RateTable other) {
        RateTable t = new RateTable();
        t.quotes.putAll(quotes);
        t.quotes.putAll(other.quotes);
        return t;
    }
}
