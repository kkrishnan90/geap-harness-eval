package com.harborline.claims.model;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Objects;

/** A first-notification-of-loss claim as received from the intake channel. */
public final class Claim {
    private final String claimId;
    private final String policyId;
    private final String claimantId;
    private final LocalDate policyInception;
    private final LocalDate lossDate;
    private final LocalDate reportedDate;
    private final BigDecimal amount;
    private final String payoutIban;

    private Claim(Builder b) {
        this.claimId = Objects.requireNonNull(b.claimId, "claimId");
        this.policyId = Objects.requireNonNull(b.policyId, "policyId");
        this.claimantId = Objects.requireNonNull(b.claimantId, "claimantId");
        this.policyInception = Objects.requireNonNull(b.policyInception, "policyInception");
        this.lossDate = Objects.requireNonNull(b.lossDate, "lossDate");
        this.reportedDate = Objects.requireNonNull(b.reportedDate, "reportedDate");
        this.amount = Objects.requireNonNull(b.amount, "amount");
        this.payoutIban = Objects.requireNonNull(b.payoutIban, "payoutIban");
        if (reportedDate.isBefore(lossDate)) {
            throw new IllegalArgumentException("reportedDate before lossDate");
        }
        if (amount.signum() <= 0) {
            throw new IllegalArgumentException("amount must be positive");
        }
    }

    public String claimId() { return claimId; }
    public String policyId() { return policyId; }
    public String claimantId() { return claimantId; }
    public LocalDate policyInception() { return policyInception; }
    public LocalDate lossDate() { return lossDate; }
    public LocalDate reportedDate() { return reportedDate; }
    public BigDecimal amount() { return amount; }
    public String payoutIban() { return payoutIban; }

    public static Builder builder() { return new Builder(); }

    public static final class Builder {
        private String claimId, policyId, claimantId, payoutIban;
        private LocalDate policyInception, lossDate, reportedDate;
        private BigDecimal amount;

        public Builder claimId(String v) { this.claimId = v; return this; }
        public Builder policyId(String v) { this.policyId = v; return this; }
        public Builder claimantId(String v) { this.claimantId = v; return this; }
        public Builder policyInception(LocalDate v) { this.policyInception = v; return this; }
        public Builder lossDate(LocalDate v) { this.lossDate = v; return this; }
        public Builder reportedDate(LocalDate v) { this.reportedDate = v; return this; }
        public Builder amount(BigDecimal v) { this.amount = v; return this; }
        public Builder amount(String v) { this.amount = new BigDecimal(v); return this; }
        public Builder payoutIban(String v) { this.payoutIban = v; return this; }
        public Claim build() { return new Claim(this); }
    }
}
