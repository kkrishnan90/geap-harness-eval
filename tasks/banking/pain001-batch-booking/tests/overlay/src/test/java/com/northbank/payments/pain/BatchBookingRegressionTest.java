package com.northbank.payments.pain;

import com.northbank.payments.pain.booking.DebitBookingPlanner;
import com.northbank.payments.pain.booking.DebitEntry;
import com.northbank.payments.pain.model.CreditTransferTransaction;
import com.northbank.payments.pain.model.PaymentInformation;
import com.northbank.payments.pain.parser.Pain001Parser;
import com.northbank.payments.pain.validation.PaymentValidator;
import com.northbank.payments.pain.validation.ValidationIssue;
import testkit.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

import static testkit.Assert.*;

/** Behaviour that must not change when batch booking support is added. */
public class BatchBookingRegressionTest {
    static final String URGENT_NO_SUM = "<Document xmlns=\"urn:iso:std:iso:20022:tech:xsd:pain.001.001.09\"><CstmrCdtTrfInitn>"
            + "<GrpHdr><MsgId>M1</MsgId><CreDtTm>2025-03-14T09:00:00</CreDtTm><NbOfTxs>2</NbOfTxs></GrpHdr>"
            + "<PmtInf><PmtInfId>P-URG</PmtInfId><PmtMtd>TRF</PmtMtd><PmtTpInf><SvcLvl><Cd>URGP</Cd></SvcLvl></PmtTpInf>"
            + "<ReqdExctnDt><Dt>2025-03-14</Dt></ReqdExctnDt><Dbtr><Nm>D</Nm></Dbtr>"
            + "<DbtrAcct><Id><IBAN>DE89370400440532013000</IBAN></Id></DbtrAcct>"
            + "<CdtTrfTxInf><PmtId><EndToEndId>E1</EndToEndId></PmtId><Amt><InstdAmt Ccy=\"EUR\">10.00</InstdAmt></Amt>"
            + "<Cdtr><Nm>C</Nm></Cdtr><CdtrAcct><Id><IBAN>NL91ABNA0417164300</IBAN></Id></CdtrAcct></CdtTrfTxInf>"
            + "<CdtTrfTxInf><PmtId><EndToEndId>E2</EndToEndId></PmtId><Amt><InstdAmt Ccy=\"USD\">20.00</InstdAmt></Amt>"
            + "<Cdtr><Nm>C2</Nm></Cdtr><CdtrAcct><Id><IBAN>NL91ABNA0417164300</IBAN></Id></CdtrAcct></CdtTrfTxInf>"
            + "</PmtInf></CstmrCdtTrfInitn></Document>";

    @Test
    public void urgentWithoutFlagNeedsNoControlSum() throws Exception {
        List<ValidationIssue> issues = new PaymentValidator(LocalDate.of(2025, 3, 14))
                .validate(new Pain001Parser().parse(URGENT_NO_SUM));
        assertTrue(issues.isEmpty(), issues.toString());
    }

    @Test
    public void instantPaymentsBookedIndividually() {
        PaymentInformation p = PaymentInformation.builder().paymentInformationId("INST-1").paymentMethod("TRF")
                .localInstrument("INST").debtorIban("DE89370400440532013000")
                .addTransaction(CreditTransferTransaction.builder().endToEndId("A").amount(new BigDecimal("1.00"))
                        .currency("EUR").creditorIban("NL91ABNA0417164300").build())
                .addTransaction(CreditTransferTransaction.builder().endToEndId("B").amount(new BigDecimal("2.00"))
                        .currency("EUR").creditorIban("NL91ABNA0417164300").build())
                .build();
        List<DebitEntry> entries = new DebitBookingPlanner().plan(p);
        assertEquals(2, entries.size(), entries.toString());
        assertEquals("B", entries.get(1).getReference());
    }
}
