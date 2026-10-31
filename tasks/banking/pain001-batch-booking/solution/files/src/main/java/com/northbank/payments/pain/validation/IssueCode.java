package com.northbank.payments.pain.validation;

/**
 * Catalogue of validation findings. Names are referenced by the ops runbook and
 * monitoring -- never rename an existing constant.
 */
public enum IssueCode {
    GRPHDR_NB_OF_TXS_MISMATCH(Severity.ERROR, "GrpHdr/NbOfTxs does not match the number of transactions"),
    GRPHDR_CTRL_SUM_MISMATCH(Severity.ERROR, "GrpHdr/CtrlSum does not match the sum of instructed amounts"),
    PMTINF_NB_OF_TXS_MISMATCH(Severity.ERROR, "PmtInf/NbOfTxs does not match the number of transactions"),
    PMTINF_CTRL_SUM_MISMATCH(Severity.ERROR, "PmtInf/CtrlSum does not match the sum of instructed amounts"),
    UNSUPPORTED_PAYMENT_METHOD(Severity.ERROR, "PmtMtd must be TRF"),
    DUPLICATE_END_TO_END_ID(Severity.ERROR, "EndToEndId is not unique within the message"),
    INVALID_AMOUNT(Severity.ERROR, "instructed amount must be positive with at most 2 decimals"),
    EXECUTION_DATE_IN_PAST(Severity.ERROR, "requested execution date is before the processing date"),
    EXECUTION_DATE_TOO_FAR(Severity.WARNING, "requested execution date is more than 365 days ahead"),
    MISSING_CREDITOR_NAME(Severity.WARNING, "creditor name is missing"),
    BATCH_BOOKING_NOT_ALLOWED(Severity.ERROR, "batch booking requested for urgent or instant payments"),
    BATCH_CTRL_SUM_MISSING(Severity.ERROR, "PmtInf/CtrlSum is mandatory for batch booking"),
    BATCH_MIXED_CURRENCY(Severity.ERROR, "all transactions of a batch-booked PmtInf must use one currency");

    private final Severity severity;
    private final String description;

    IssueCode(Severity severity, String description) {
        this.severity = severity;
        this.description = description;
    }

    public Severity getSeverity() { return severity; }
    public String getDescription() { return description; }
}
