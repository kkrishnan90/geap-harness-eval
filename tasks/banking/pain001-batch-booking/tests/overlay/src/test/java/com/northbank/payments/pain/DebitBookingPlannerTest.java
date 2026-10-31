package com.northbank.payments.pain;

import com.northbank.payments.pain.booking.DebitBookingPlanner;
import com.northbank.payments.pain.booking.DebitEntry;
import com.northbank.payments.pain.model.CreditTransferTransaction;
import com.northbank.payments.pain.model.PaymentInformation;
import testkit.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

import static testkit.Assert.*;

public class DebitBookingPlannerTest {
    static CreditTransferTransaction tx(String e2e, String amount) {
        return CreditTransferTransaction.builder().endToEndId(e2e).amount(new BigDecimal(amount)).currency("EUR")
                .creditorName("Creditor " + e2e).creditorIban("NL91ABNA0417164300").build();
    }

    @Test
    public void urgentPaymentsAreBookedPerTransaction() {
        PaymentInformation p = PaymentInformation.builder().paymentInformationId("TREASURY-0314")
                .paymentMethod("TRF").serviceLevel("URGP").requestedExecutionDate(LocalDate.of(2025, 3, 14))
                .debtorName("ACME").debtorIban("DE89370400440532013000")
                .addTransaction(tx("FX-SETTLE-1", "250000.00")).addTransaction(tx("FX-SETTLE-2", "125000.00"))
                .build();
        List<DebitEntry> entries = new DebitBookingPlanner().plan(p);
        assertEquals(2, entries.size());
        assertEquals("FX-SETTLE-1", entries.get(0).getReference());
        assertAmount("250000.00", entries.get(0).getAmount(), "first debit");
        assertEquals(List.of("FX-SETTLE-2"), entries.get(1).getEndToEndIds());
        assertEquals("DE89370400440532013000", entries.get(1).getDebtorIban());
    }
}
