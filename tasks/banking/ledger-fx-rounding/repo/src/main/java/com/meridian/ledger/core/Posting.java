package com.meridian.ledger.core;

import com.meridian.ledger.money.Money;

import java.math.BigDecimal;
import java.util.Objects;

/**
 * One line of a journal entry. {@code amount} is in the account currency (may be zero for a
 * pure revaluation line); {@code functionalAmount} is the same line in the ledger's functional
 * currency, already rounded to its minor unit. Both are non-negative; the side gives the sign.
 */
public final class Posting {
    private final Account account;
    private final Side side;
    private final Money amount;
    private final BigDecimal functionalAmount;

    public Posting(Account account, Side side, Money amount, BigDecimal functionalAmount) {
        this.account = Objects.requireNonNull(account);
        this.side = Objects.requireNonNull(side);
        this.amount = Objects.requireNonNull(amount);
        this.functionalAmount = Objects.requireNonNull(functionalAmount);
    }

    public Account getAccount() { return account; }
    public Side getSide() { return side; }
    public Money getAmount() { return amount; }
    public BigDecimal getFunctionalAmount() { return functionalAmount; }

    /** Signed (debit-positive) amount in account currency. */
    public BigDecimal signedAmount() { return side == Side.DEBIT ? amount.getAmount() : amount.getAmount().negate(); }

    /** Signed (debit-positive) functional amount. */
    public BigDecimal signedFunctional() { return side == Side.DEBIT ? functionalAmount : functionalAmount.negate(); }

    @Override
    public String toString() {
        return side + " " + account.getCode() + " " + amount + " [" + functionalAmount.toPlainString() + "]";
    }
}
