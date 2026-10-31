package com.northbank.payments.pain.booking;

import com.northbank.payments.pain.model.CreditTransferTransaction;
import com.northbank.payments.pain.model.CustomerCreditTransferInitiation;
import com.northbank.payments.pain.model.PaymentInformation;

import java.util.ArrayList;
import java.util.List;

/**
 * Decides which debit entries the booking engine posts on the debtor account for an
 * accepted message. Callers only invoke it for messages without validation errors.
 */
public final class DebitBookingPlanner {

    public List<DebitEntry> plan(CustomerCreditTransferInitiation msg) {
        List<DebitEntry> out = new ArrayList<>();
        for (PaymentInformation p : msg.getPaymentInformations()) out.addAll(plan(p));
        return out;
    }

    /** Entries for one PmtInf, in file order. */
    public List<DebitEntry> plan(PaymentInformation p) {
        List<DebitEntry> out = new ArrayList<>();
        if (p.isBatchBooking()) {
            List<String> ids = new ArrayList<>();
            for (CreditTransferTransaction tx : p.getTransactions()) ids.add(tx.getEndToEndId());
            out.add(new DebitEntry(p.getDebtorIban(), p.sumOfAmounts(), p.getTransactions().get(0).getCurrency(),
                    p.getPaymentInformationId(), ids));
            return out;
        }
        for (CreditTransferTransaction tx : p.getTransactions()) {
            out.add(new DebitEntry(p.getDebtorIban(), tx.getAmount(), tx.getCurrency(), tx.getEndToEndId(),
                    List.of(tx.getEndToEndId())));
        }
        return out;
    }
}
