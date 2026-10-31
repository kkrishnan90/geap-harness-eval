package com.northbank.payments.pain.model;

import java.util.List;
import java.util.Objects;

/** Root of a parsed pain.001 message. */
public final class CustomerCreditTransferInitiation {
    private final GroupHeader groupHeader;
    private final List<PaymentInformation> paymentInformations;

    public CustomerCreditTransferInitiation(GroupHeader groupHeader, List<PaymentInformation> paymentInformations) {
        this.groupHeader = Objects.requireNonNull(groupHeader, "groupHeader");
        this.paymentInformations = List.copyOf(paymentInformations);
    }

    public GroupHeader getGroupHeader() { return groupHeader; }
    public List<PaymentInformation> getPaymentInformations() { return paymentInformations; }

    public int countTransactions() {
        int n = 0;
        for (PaymentInformation p : paymentInformations) n += p.getTransactions().size();
        return n;
    }
}
