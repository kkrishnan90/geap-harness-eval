package com.northbank.payments.pain.model;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Objects;

/** One PmtInf block: a group of transfers debited from the same account on the same date. */
public final class PaymentInformation {
    private final String paymentInformationId;
    private final String paymentMethod;
    private final Boolean batchBooking;
    private final Integer numberOfTransactions;
    private final BigDecimal controlSum;
    private final String serviceLevel;
    private final String localInstrument;
    private final LocalDate requestedExecutionDate;
    private final String debtorName;
    private final String debtorIban;
    private final String debtorBic;
    private final List<CreditTransferTransaction> transactions;

    private PaymentInformation(Builder b) {
        this.paymentInformationId = Objects.requireNonNull(b.paymentInformationId, "paymentInformationId");
        this.paymentMethod = b.paymentMethod;
        this.batchBooking = b.batchBooking;
        this.numberOfTransactions = b.numberOfTransactions;
        this.controlSum = b.controlSum;
        this.serviceLevel = b.serviceLevel;
        this.localInstrument = b.localInstrument;
        this.requestedExecutionDate = b.requestedExecutionDate;
        this.debtorName = b.debtorName;
        this.debtorIban = b.debtorIban;
        this.debtorBic = b.debtorBic;
        this.transactions = List.copyOf(b.transactions);
    }

    public String getPaymentInformationId() { return paymentInformationId; }
    public String getPaymentMethod() { return paymentMethod; }

    /** BtchBookg as stated in the file, or null if absent. */
    public Boolean getBatchBooking() { return batchBooking; }

    /**
     * Effective batch booking flag: the stated BtchBookg value; if absent, false for urgent
     * (SvcLvl URGP) or instant (LclInstrm INST) payments and true otherwise.
     */
    public boolean isBatchBooking() {
        if (batchBooking != null) return batchBooking;
        return !isUrgentOrInstant();
    }

    /** SvcLvl/Cd is URGP or LclInstrm/Cd is INST. */
    public boolean isUrgentOrInstant() {
        return "URGP".equals(serviceLevel) || "INST".equals(localInstrument);
    }
    /** NbOfTxs as stated in the file, or null if absent. */
    public Integer getNumberOfTransactions() { return numberOfTransactions; }
    /** CtrlSum as stated in the file, or null if absent. */
    public BigDecimal getControlSum() { return controlSum; }
    /** PmtTpInf/SvcLvl/Cd, e.g. SEPA or URGP; null if absent. */
    public String getServiceLevel() { return serviceLevel; }
    /** PmtTpInf/LclInstrm/Cd, e.g. INST; null if absent. */
    public String getLocalInstrument() { return localInstrument; }
    public LocalDate getRequestedExecutionDate() { return requestedExecutionDate; }
    public String getDebtorName() { return debtorName; }
    public String getDebtorIban() { return debtorIban; }
    public String getDebtorBic() { return debtorBic; }
    public List<CreditTransferTransaction> getTransactions() { return transactions; }

    public BigDecimal sumOfAmounts() {
        BigDecimal s = BigDecimal.ZERO;
        for (CreditTransferTransaction t : transactions) s = s.add(t.getAmount());
        return s;
    }

    public static Builder builder() { return new Builder(); }

    public static final class Builder {
        private String paymentInformationId;
        private String paymentMethod;
        private Boolean batchBooking;
        private Integer numberOfTransactions;
        private BigDecimal controlSum;
        private String serviceLevel;
        private String localInstrument;
        private LocalDate requestedExecutionDate;
        private String debtorName;
        private String debtorIban;
        private String debtorBic;
        private final java.util.ArrayList<CreditTransferTransaction> transactions = new java.util.ArrayList<>();

        public Builder paymentInformationId(String v) { this.paymentInformationId = v; return this; }
        public Builder paymentMethod(String v) { this.paymentMethod = v; return this; }
        public Builder batchBooking(Boolean v) { this.batchBooking = v; return this; }
        public Builder numberOfTransactions(Integer v) { this.numberOfTransactions = v; return this; }
        public Builder controlSum(BigDecimal v) { this.controlSum = v; return this; }
        public Builder serviceLevel(String v) { this.serviceLevel = v; return this; }
        public Builder localInstrument(String v) { this.localInstrument = v; return this; }
        public Builder requestedExecutionDate(LocalDate v) { this.requestedExecutionDate = v; return this; }
        public Builder debtorName(String v) { this.debtorName = v; return this; }
        public Builder debtorIban(String v) { this.debtorIban = v; return this; }
        public Builder debtorBic(String v) { this.debtorBic = v; return this; }
        public Builder addTransaction(CreditTransferTransaction t) { this.transactions.add(t); return this; }
        public PaymentInformation build() { return new PaymentInformation(this); }
    }
}
