package com.northbank.payments.pain.booking;

import java.math.BigDecimal;
import java.util.List;
import java.util.Objects;

/** One debit to be posted on the debtor's account by the core booking engine. */
public final class DebitEntry {
    private final String debtorIban;
    private final BigDecimal amount;
    private final String currency;
    private final String reference;
    private final List<String> endToEndIds;

    public DebitEntry(String debtorIban, BigDecimal amount, String currency, String reference, List<String> endToEndIds) {
        this.debtorIban = Objects.requireNonNull(debtorIban);
        this.amount = Objects.requireNonNull(amount);
        this.currency = Objects.requireNonNull(currency);
        this.reference = Objects.requireNonNull(reference);
        this.endToEndIds = List.copyOf(endToEndIds);
    }

    public String getDebtorIban() { return debtorIban; }
    public BigDecimal getAmount() { return amount; }
    public String getCurrency() { return currency; }
    /** Shown on the debtor's statement. */
    public String getReference() { return reference; }
    /** The transactions covered by this debit, in file order. */
    public List<String> getEndToEndIds() { return endToEndIds; }

    @Override
    public String toString() {
        return "DebitEntry{" + reference + " " + amount.toPlainString() + " " + currency + " " + endToEndIds + "}";
    }
}
