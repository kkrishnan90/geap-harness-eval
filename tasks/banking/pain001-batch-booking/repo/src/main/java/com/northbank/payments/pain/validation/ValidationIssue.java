package com.northbank.payments.pain.validation;

import java.util.Objects;

/** A single validation finding, located by PmtInfId and (optionally) EndToEndId. */
public final class ValidationIssue {
    private final IssueCode code;
    private final String paymentInformationId;
    private final String endToEndId;
    private final String detail;

    public ValidationIssue(IssueCode code, String paymentInformationId, String endToEndId, String detail) {
        this.code = Objects.requireNonNull(code);
        this.paymentInformationId = paymentInformationId;
        this.endToEndId = endToEndId;
        this.detail = detail;
    }

    public IssueCode getCode() { return code; }
    public Severity getSeverity() { return code.getSeverity(); }
    /** null for message-level issues. */
    public String getPaymentInformationId() { return paymentInformationId; }
    /** null unless the issue concerns one transaction. */
    public String getEndToEndId() { return endToEndId; }
    public String getDetail() { return detail; }

    @Override
    public String toString() {
        return code + "[" + paymentInformationId + (endToEndId == null ? "" : "/" + endToEndId) + "] " + detail;
    }
}
