package com.northbank.payments.pain;

import com.northbank.payments.pain.model.CreditTransferTransaction;
import com.northbank.payments.pain.model.CustomerCreditTransferInitiation;
import com.northbank.payments.pain.model.PaymentInformation;
import com.northbank.payments.pain.parser.ParseException;
import com.northbank.payments.pain.parser.Pain001Parser;
import testkit.Test;

import java.io.FileInputStream;
import java.io.InputStream;
import java.time.LocalDate;

import static testkit.Assert.*;

public class Pain001ParserTest {
    static final String FIXTURE = "src/test/resources/pain001/two-batches.xml";

    static CustomerCreditTransferInitiation fixture() throws Exception {
        try (InputStream in = new FileInputStream(FIXTURE)) {
            return new Pain001Parser().parse(in);
        }
    }

    static String minimal(String pmtInfExtra) {
        return "<Document xmlns=\"urn:iso:std:iso:20022:tech:xsd:pain.001.001.09\"><CstmrCdtTrfInitn>"
                + "<GrpHdr><MsgId>M1</MsgId><CreDtTm>2025-03-14T09:00:00+01:00</CreDtTm><NbOfTxs>1</NbOfTxs></GrpHdr>"
                + "<PmtInf><PmtInfId>P1</PmtInfId><PmtMtd>TRF</PmtMtd>" + pmtInfExtra
                + "<ReqdExctnDt>2025-03-17</ReqdExctnDt><Dbtr><Nm>D</Nm></Dbtr>"
                + "<DbtrAcct><Id><IBAN>DE89370400440532013000</IBAN></Id></DbtrAcct>"
                + "<CdtTrfTxInf><PmtId><EndToEndId>E1</EndToEndId></PmtId><Amt><InstdAmt Ccy=\"EUR\">10.00</InstdAmt></Amt>"
                + "<Cdtr><Nm>C</Nm></Cdtr><CdtrAcct><Id><IBAN>NL91ABNA0417164300</IBAN></Id></CdtrAcct></CdtTrfTxInf>"
                + "</PmtInf></CstmrCdtTrfInitn></Document>";
    }

    @Test
    public void parsesGroupHeader() throws Exception {
        CustomerCreditTransferInitiation m = fixture();
        assertEquals("ACME-20250314-0001", m.getGroupHeader().getMessageId());
        assertEquals(3, m.getGroupHeader().getNumberOfTransactions());
        assertAmount("4350.75", m.getGroupHeader().getControlSum(), "GrpHdr/CtrlSum");
        assertEquals("ACME Logistics GmbH", m.getGroupHeader().getInitiatingPartyName());
    }

    @Test
    public void parsesPaymentInformationBlocks() throws Exception {
        CustomerCreditTransferInitiation m = fixture();
        assertEquals(2, m.getPaymentInformations().size());
        PaymentInformation p = m.getPaymentInformations().get(0);
        assertEquals("ACME-SUPPLIERS-0314", p.getPaymentInformationId());
        assertEquals("SEPA", p.getServiceLevel());
        assertNull(p.getLocalInstrument(), "LclInstrm");
        assertEquals(LocalDate.of(2025, 3, 17), p.getRequestedExecutionDate());
        assertEquals("COBADEFFXXX", p.getDebtorBic());
        assertEquals(2, p.getTransactions().size());
        assertAmount("3100.75", p.sumOfAmounts(), "sum");
    }

    @Test
    public void parsesTransactions() throws Exception {
        CreditTransferTransaction t = fixture().getPaymentInformations().get(0).getTransactions().get(0);
        assertEquals("INV-2025-0412", t.getEndToEndId());
        assertAmount("1850.50", t.getAmount(), "amount");
        assertEquals("EUR", t.getCurrency());
        assertEquals("BNPAFRPPXXX", t.getCreditorBic());
        assertEquals("FR1420041010050500013M02606", t.getCreditorIban());
        assertEquals("Invoice 2025-0412", t.getRemittanceInfo());
    }

    @Test
    public void acceptsOffsetDateTimeAndBareDate() throws Exception {
        CustomerCreditTransferInitiation m = new Pain001Parser().parse(minimal(""));
        assertEquals(LocalDate.of(2025, 3, 17), m.getPaymentInformations().get(0).getRequestedExecutionDate());
        assertNull(m.getPaymentInformations().get(0).getControlSum(), "CtrlSum");
    }

    @Test
    public void rejectsDoctype() {
        String xml = "<?xml version=\"1.0\"?><!DOCTYPE x [<!ENTITY e SYSTEM \"file:///etc/passwd\">]>" + minimal("");
        assertThrows(ParseException.class, () -> new Pain001Parser().parse(xml));
    }

    @Test
    public void rejectsWrongNamespace() {
        String xml = minimal("").replace("pain.001.001.09", "pain.001.001.03");
        assertThrows(ParseException.class, () -> new Pain001Parser().parse(xml));
    }

    @Test
    public void missingMandatoryElementNamesIt() {
        String xml = minimal("").replace("<PmtMtd>TRF</PmtMtd>", "");
        ParseException e = assertThrows(ParseException.class, () -> new Pain001Parser().parse(xml));
        assertTrue(e.getMessage().contains("PmtMtd"), e.getMessage());
    }

    @Test
    public void invalidAmountRejected() {
        String xml = minimal("").replace(">10.00<", ">10,00<");
        assertThrows(ParseException.class, () -> new Pain001Parser().parse(xml));
    }
}
