package com.northbank.payments.pain.validation;

import com.northbank.payments.pain.model.CreditTransferTransaction;
import com.northbank.payments.pain.model.CustomerCreditTransferInitiation;
import com.northbank.payments.pain.model.GroupHeader;
import com.northbank.payments.pain.model.PaymentInformation;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Pre-booking validation of a parsed pain.001 message. Returns all findings in a
 * stable order: message-level issues first, then per PmtInf in file order
 * (PmtInf-level issues before transaction-level issues).
 */
public final class PaymentValidator {
    private final LocalDate processingDate;

    public PaymentValidator(LocalDate processingDate) {
        this.processingDate = processingDate;
    }

    public List<ValidationIssue> validate(CustomerCreditTransferInitiation msg) {
        List<ValidationIssue> issues = new ArrayList<>();
        GroupHeader hdr = msg.getGroupHeader();

        if (hdr.getNumberOfTransactions() != msg.countTransactions()) {
            issues.add(new ValidationIssue(IssueCode.GRPHDR_NB_OF_TXS_MISMATCH, null, null,
                    "stated " + hdr.getNumberOfTransactions() + ", found " + msg.countTransactions()));
        }
        BigDecimal total = BigDecimal.ZERO;
        for (PaymentInformation p : msg.getPaymentInformations()) total = total.add(p.sumOfAmounts());
        if (hdr.getControlSum() != null && hdr.getControlSum().compareTo(total) != 0) {
            issues.add(new ValidationIssue(IssueCode.GRPHDR_CTRL_SUM_MISMATCH, null, null,
                    "stated " + hdr.getControlSum().toPlainString() + ", computed " + total.toPlainString()));
        }

        Set<String> endToEndIds = new HashSet<>();
        for (PaymentInformation p : msg.getPaymentInformations()) {
            validatePaymentInformation(p, issues);
            for (CreditTransferTransaction tx : p.getTransactions()) {
                validateTransaction(p, tx, endToEndIds, issues);
            }
        }
        return issues;
    }

    private void validatePaymentInformation(PaymentInformation p, List<ValidationIssue> issues) {
        String id = p.getPaymentInformationId();
        if (!"TRF".equals(p.getPaymentMethod())) {
            issues.add(new ValidationIssue(IssueCode.UNSUPPORTED_PAYMENT_METHOD, id, null, "PmtMtd=" + p.getPaymentMethod()));
        }
        if (p.getNumberOfTransactions() != null && p.getNumberOfTransactions() != p.getTransactions().size()) {
            issues.add(new ValidationIssue(IssueCode.PMTINF_NB_OF_TXS_MISMATCH, id, null,
                    "stated " + p.getNumberOfTransactions() + ", found " + p.getTransactions().size()));
        }
        if (p.getControlSum() != null && p.getControlSum().compareTo(p.sumOfAmounts()) != 0) {
            issues.add(new ValidationIssue(IssueCode.PMTINF_CTRL_SUM_MISMATCH, id, null,
                    "stated " + p.getControlSum().toPlainString() + ", computed " + p.sumOfAmounts().toPlainString()));
        }
        validateBatchBooking(p, issues);
        LocalDate d = p.getRequestedExecutionDate();
        if (d != null && processingDate != null) {
            if (d.isBefore(processingDate)) {
                issues.add(new ValidationIssue(IssueCode.EXECUTION_DATE_IN_PAST, id, null, d.toString()));
            } else if (d.isAfter(processingDate.plusDays(365))) {
                issues.add(new ValidationIssue(IssueCode.EXECUTION_DATE_TOO_FAR, id, null, d.toString()));
            }
        }
    }

    private void validateBatchBooking(PaymentInformation p, List<ValidationIssue> issues) {
        String id = p.getPaymentInformationId();
        if (Boolean.TRUE.equals(p.getBatchBooking()) && p.isUrgentOrInstant()) {
            issues.add(new ValidationIssue(IssueCode.BATCH_BOOKING_NOT_ALLOWED, id, null,
                    "SvcLvl=" + p.getServiceLevel() + " LclInstrm=" + p.getLocalInstrument()));
            return;
        }
        if (!p.isBatchBooking()) return;
        if (p.getControlSum() == null) {
            issues.add(new ValidationIssue(IssueCode.BATCH_CTRL_SUM_MISSING, id, null, ""));
        }
        Set<String> currencies = new java.util.TreeSet<>();
        for (CreditTransferTransaction tx : p.getTransactions()) currencies.add(tx.getCurrency());
        if (currencies.size() > 1) {
            issues.add(new ValidationIssue(IssueCode.BATCH_MIXED_CURRENCY, id, null, currencies.toString()));
        }
    }

    private void validateTransaction(PaymentInformation p, CreditTransferTransaction tx, Set<String> seen,
                                     List<ValidationIssue> issues) {
        String id = p.getPaymentInformationId();
        if (!seen.add(tx.getEndToEndId())) {
            issues.add(new ValidationIssue(IssueCode.DUPLICATE_END_TO_END_ID, id, tx.getEndToEndId(), tx.getEndToEndId()));
        }
        BigDecimal a = tx.getAmount();
        if (a.signum() <= 0 || a.stripTrailingZeros().scale() > 2) {
            issues.add(new ValidationIssue(IssueCode.INVALID_AMOUNT, id, tx.getEndToEndId(), a.toPlainString()));
        }
        if (tx.getCreditorName() == null || tx.getCreditorName().isBlank()) {
            issues.add(new ValidationIssue(IssueCode.MISSING_CREDITOR_NAME, id, tx.getEndToEndId(), ""));
        }
    }

    public static boolean hasErrors(List<ValidationIssue> issues) {
        for (ValidationIssue i : issues) if (i.getSeverity() == Severity.ERROR) return true;
        return false;
    }
}
