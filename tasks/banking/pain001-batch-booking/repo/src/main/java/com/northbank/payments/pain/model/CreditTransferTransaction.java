package com.northbank.payments.pain.model;

import java.math.BigDecimal;
import java.util.Objects;

/** One CdtTrfTxInf block: a single credit transfer to one creditor. */
public final class CreditTransferTransaction {
    private final String endToEndId;
    private final BigDecimal amount;
    private final String currency;
    private final String creditorName;
    private final String creditorIban;
    private final String creditorBic;
    private final String remittanceInfo;

    private CreditTransferTransaction(Builder b) {
        this.endToEndId = Objects.requireNonNull(b.endToEndId, "endToEndId");
        this.amount = Objects.requireNonNull(b.amount, "amount");
        this.currency = Objects.requireNonNull(b.currency, "currency");
        this.creditorName = b.creditorName;
        this.creditorIban = b.creditorIban;
        this.creditorBic = b.creditorBic;
        this.remittanceInfo = b.remittanceInfo;
    }

    public String getEndToEndId() { return endToEndId; }
    public BigDecimal getAmount() { return amount; }
    public String getCurrency() { return currency; }
    public String getCreditorName() { return creditorName; }
    public String getCreditorIban() { return creditorIban; }
    public String getCreditorBic() { return creditorBic; }
    public String getRemittanceInfo() { return remittanceInfo; }

    public static Builder builder() { return new Builder(); }

    public static final class Builder {
        private String endToEndId;
        private BigDecimal amount;
        private String currency;
        private String creditorName;
        private String creditorIban;
        private String creditorBic;
        private String remittanceInfo;

        public Builder endToEndId(String v) { this.endToEndId = v; return this; }
        public Builder amount(BigDecimal v) { this.amount = v; return this; }
        public Builder currency(String v) { this.currency = v; return this; }
        public Builder creditorName(String v) { this.creditorName = v; return this; }
        public Builder creditorIban(String v) { this.creditorIban = v; return this; }
        public Builder creditorBic(String v) { this.creditorBic = v; return this; }
        public Builder remittanceInfo(String v) { this.remittanceInfo = v; return this; }
        public CreditTransferTransaction build() { return new CreditTransferTransaction(this); }
    }
}
