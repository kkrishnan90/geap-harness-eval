package com.meridian.ledger.money;

import java.math.BigDecimal;
import java.util.Currency;
import java.util.Objects;

/** Immutable amount in a currency. Arithmetic is exact; use {@link #rounded()} to apply the policy. */
public final class Money implements Comparable<Money> {
    private final BigDecimal amount;
    private final Currency currency;

    private Money(BigDecimal amount, Currency currency) {
        this.amount = Objects.requireNonNull(amount, "amount");
        this.currency = Objects.requireNonNull(currency, "currency");
    }

    public static Money of(BigDecimal amount, Currency currency) { return new Money(amount, currency); }

    public static Money of(String amount, String currencyCode) {
        return new Money(new BigDecimal(amount), Currency.getInstance(currencyCode));
    }

    public static Money zero(Currency currency) {
        return new Money(BigDecimal.ZERO.setScale(Rounding.minorUnits(currency)), currency);
    }

    public BigDecimal getAmount() { return amount; }
    public Currency getCurrency() { return currency; }

    public Money add(Money other) { requireSame(other); return new Money(amount.add(other.amount), currency); }
    public Money subtract(Money other) { requireSame(other); return new Money(amount.subtract(other.amount), currency); }
    public Money negate() { return new Money(amount.negate(), currency); }
    public Money abs() { return new Money(amount.abs(), currency); }
    public int signum() { return amount.signum(); }
    public boolean isZero() { return amount.signum() == 0; }

    /** This amount rounded to the currency's minor unit with the group rounding policy. */
    public Money rounded() { return new Money(Rounding.round(amount, currency), currency); }

    private void requireSame(Money other) {
        if (!currency.equals(other.currency)) {
            throw new CurrencyMismatchException(currency + " vs " + other.currency);
        }
    }

    @Override
    public int compareTo(Money o) { requireSame(o); return amount.compareTo(o.amount); }

    /** Equal if same currency and numerically equal amount (scale ignored). */
    @Override
    public boolean equals(Object o) {
        if (!(o instanceof Money)) return false;
        Money m = (Money) o;
        return currency.equals(m.currency) && amount.compareTo(m.amount) == 0;
    }

    @Override
    public int hashCode() { return Objects.hash(currency, amount.stripTrailingZeros()); }

    @Override
    public String toString() { return amount.toPlainString() + " " + currency.getCurrencyCode(); }
}
