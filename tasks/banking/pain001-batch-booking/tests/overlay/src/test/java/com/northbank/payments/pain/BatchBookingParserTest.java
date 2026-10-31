package com.northbank.payments.pain;

import com.northbank.payments.pain.model.PaymentInformation;
import com.northbank.payments.pain.parser.ParseException;
import com.northbank.payments.pain.parser.Pain001Parser;
import testkit.Test;

import static testkit.Assert.*;

public class BatchBookingParserTest {
    /** Builds a one-PmtInf pain.001 message. tpInf/btch/ctrlSum may be null (= element omitted). */
    static String msg(String btch, String ctrlSum, String svcLvl, String lclInstrm, String... txs) {
        StringBuilder sb = new StringBuilder();
        sb.append("<?xml version=\"1.0\" encoding=\"UTF-8\"?>")
          .append("<Document xmlns=\"urn:iso:std:iso:20022:tech:xsd:pain.001.001.09\"><CstmrCdtTrfInitn>")
          .append("<GrpHdr><MsgId>BB-TEST-1</MsgId><CreDtTm>2025-03-14T10:00:00</CreDtTm>")
          .append("<NbOfTxs>").append(txs.length / 3).append("</NbOfTxs></GrpHdr>")
          .append("<PmtInf><PmtInfId>PI-BATCH-01</PmtInfId><PmtMtd>TRF</PmtMtd>");
        if (btch != null) sb.append("<BtchBookg>").append(btch).append("</BtchBookg>");
        sb.append("<NbOfTxs>").append(txs.length / 3).append("</NbOfTxs>");
        if (ctrlSum != null) sb.append("<CtrlSum>").append(ctrlSum).append("</CtrlSum>");
        if (svcLvl != null || lclInstrm != null) {
            sb.append("<PmtTpInf>");
            if (svcLvl != null) sb.append("<SvcLvl><Cd>").append(svcLvl).append("</Cd></SvcLvl>");
            if (lclInstrm != null) sb.append("<LclInstrm><Cd>").append(lclInstrm).append("</Cd></LclInstrm>");
            sb.append("</PmtTpInf>");
        }
        sb.append("<ReqdExctnDt><Dt>2025-03-17</Dt></ReqdExctnDt><Dbtr><Nm>ACME Logistics GmbH</Nm></Dbtr>")
          .append("<DbtrAcct><Id><IBAN>DE89370400440532013000</IBAN></Id></DbtrAcct>");
        for (int i = 0; i < txs.length; i += 3) {
            sb.append("<CdtTrfTxInf><PmtId><EndToEndId>").append(txs[i]).append("</EndToEndId></PmtId>")
              .append("<Amt><InstdAmt Ccy=\"").append(txs[i + 2]).append("\">").append(txs[i + 1]).append("</InstdAmt></Amt>")
              .append("<Cdtr><Nm>Creditor ").append(i).append("</Nm></Cdtr>")
              .append("<CdtrAcct><Id><IBAN>NL91ABNA0417164300</IBAN></Id></CdtrAcct></CdtTrfTxInf>");
        }
        sb.append("</PmtInf></CstmrCdtTrfInitn></Document>");
        return sb.toString();
    }

    static PaymentInformation pmtInf(String xml) throws Exception {
        return new Pain001Parser().parse(xml).getPaymentInformations().get(0);
    }

    @Test
    public void explicitTrue() throws Exception {
        PaymentInformation p = pmtInf(msg("true", "10.00", null, null, "E1", "10.00", "EUR"));
        assertEquals(Boolean.TRUE, p.getBatchBooking());
        assertTrue(p.isBatchBooking());
    }

    @Test
    public void explicitFalse() throws Exception {
        PaymentInformation p = pmtInf(msg("false", null, null, null, "E1", "10.00", "EUR"));
        assertEquals(Boolean.FALSE, p.getBatchBooking());
        assertFalse(p.isBatchBooking());
    }

    @Test
    public void numericLexicalForms() throws Exception {
        assertEquals(Boolean.TRUE, pmtInf(msg("1", "10.00", null, null, "E1", "10.00", "EUR")).getBatchBooking());
        assertEquals(Boolean.FALSE, pmtInf(msg("0", null, null, null, "E1", "10.00", "EUR")).getBatchBooking());
        assertEquals(Boolean.TRUE, pmtInf(msg("  true\n", "10.00", null, null, "E1", "10.00", "EUR")).getBatchBooking());
    }

    @Test
    public void absentDefaultsToTrueForStandardPayments() throws Exception {
        PaymentInformation p = pmtInf(msg(null, "10.00", "SEPA", null, "E1", "10.00", "EUR"));
        assertNull(p.getBatchBooking(), "stated BtchBookg");
        assertTrue(p.isBatchBooking());
    }

    @Test
    public void absentDefaultsToFalseForUrgentAndInstant() throws Exception {
        assertFalse(pmtInf(msg(null, null, "URGP", null, "E1", "10.00", "EUR")).isBatchBooking());
        assertFalse(pmtInf(msg(null, null, "SEPA", "INST", "E1", "10.00", "EUR")).isBatchBooking());
    }

    @Test
    public void explicitFlagWinsOverDefault() throws Exception {
        assertTrue(pmtInf(msg("true", "10.00", "URGP", null, "E1", "10.00", "EUR")).isBatchBooking());
        assertFalse(pmtInf(msg("false", null, "SEPA", null, "E1", "10.00", "EUR")).isBatchBooking());
    }

    @Test
    public void invalidValueRejectedNamingElement() {
        for (String bad : new String[] {"yes", "TRUE", "", "2"}) {
            ParseException e = assertThrows(ParseException.class,
                    () -> new Pain001Parser().parse(msg(bad, "10.00", null, null, "E1", "10.00", "EUR")));
            assertTrue(e.getMessage() != null && e.getMessage().contains("BtchBookg"), "message: " + e.getMessage());
        }
    }

    @Test
    public void builderCarriesFlag() {
        PaymentInformation p = PaymentInformation.builder().paymentInformationId("X").paymentMethod("TRF")
                .batchBooking(Boolean.FALSE).build();
        assertEquals(Boolean.FALSE, p.getBatchBooking());
        assertFalse(p.isBatchBooking());
    }
}
