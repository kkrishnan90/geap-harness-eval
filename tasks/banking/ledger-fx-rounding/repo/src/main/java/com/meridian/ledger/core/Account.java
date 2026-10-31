package com.meridian.ledger.core;

import java.util.Currency;
import java.util.Objects;

/** A general-ledger account. Every account is kept in exactly one currency. */
public final class Account {
    private final String code;
    private final String name;
    private final AccountType type;
    private final Currency currency;

    public Account(String code, String name, AccountType type, Currency currency) {
        this.code = Objects.requireNonNull(code);
        this.name = Objects.requireNonNull(name);
        this.type = Objects.requireNonNull(type);
        this.currency = Objects.requireNonNull(currency);
    }

    public static Account of(String code, String name, AccountType type, String currency) {
        return new Account(code, name, type, Currency.getInstance(currency));
    }

    public String getCode() { return code; }
    public String getName() { return name; }
    public AccountType getType() { return type; }
    public Currency getCurrency() { return currency; }

    @Override
    public boolean equals(Object o) { return o instanceof Account && ((Account) o).code.equals(code); }

    @Override
    public int hashCode() { return code.hashCode(); }

    @Override
    public String toString() { return code + " " + name + " (" + currency + ")"; }
}
