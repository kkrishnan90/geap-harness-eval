package com.meridian.ledger.core;

import java.math.BigDecimal;

/** Debit-positive balance of an account: in account currency and in functional currency. */
public final class AccountBalance {
    private final Account account;
    private final BigDecimal amount;
    private final BigDecimal functional;

    public AccountBalance(Account account, BigDecimal amount, BigDecimal functional) {
        this.account = account;
        this.amount = amount;
        this.functional = functional;
    }

    public Account getAccount() { return account; }
    public BigDecimal getAmount() { return amount; }
    public BigDecimal getFunctional() { return functional; }

    @Override
    public String toString() {
        return account.getCode() + " " + amount.toPlainString() + " " + account.getCurrency()
                + " [" + functional.toPlainString() + "]";
    }
}
