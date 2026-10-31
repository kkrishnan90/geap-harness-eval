package com.northbank.payments.pain;

import com.northbank.payments.pain.booking.DebitBookingPlanner;
import com.northbank.payments.pain.booking.DebitEntry;
import com.northbank.payments.pain.model.PaymentInformation;
import com.northbank.payments.pain.parser.Pain001Parser;
import testkit.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static testkit.Assert.*;

public class BatchBookingPlannerTest {
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
    public void batchProducesOneDebitPerPaymentInformation() throws Exception {
        PaymentInformation p = pmtInf(msg("true", "1500.30", null, null,
                "INV-1", "1000.10", "EUR", "INV-2", "400.10", "EUR", "INV-3", "100.10", "EUR"));
        List<DebitEntry> entries = new DebitBookingPlanner().plan(p);
        assertEquals(1, entries.size(), entries.toString());
        DebitEntry d = entries.get(0);
        assertAmount("1500.30", d.getAmount(), "batch debit");
        assertEquals("EUR", d.getCurrency());
        assertEquals("PI-BATCH-01", d.getReference());
        assertEquals(List.of("INV-1", "INV-2", "INV-3"), d.getEndToEndIds());
        assertEquals("DE89370400440532013000", d.getDebtorIban());
    }

    @Test
    public void explicitFalseProducesOneDebitPerTransaction() throws Exception {
        PaymentInformation p = pmtInf(msg("false", null, null, null, "INV-1", "1000.10", "EUR", "INV-2", "400.10", "EUR"));
        List<DebitEntry> entries = new DebitBookingPlanner().plan(p);
        assertEquals(2, entries.size(), entries.toString());
        assertEquals("INV-1", entries.get(0).getReference());
        assertEquals(List.of("INV-2"), entries.get(1).getEndToEndIds());
    }

    @Test
    public void fixtureFileIsBatchBookedPerPmtInf() throws Exception {
        String xml = Files.readString(Path.of("src/test/resources/pain001/two-batches.xml"));
        List<DebitEntry> entries = new DebitBookingPlanner().plan(new Pain001Parser().parse(xml));
        assertEquals(2, entries.size(), entries.toString());
        assertEquals("ACME-SUPPLIERS-0314", entries.get(0).getReference());
        assertAmount("3100.75", entries.get(0).getAmount(), "suppliers batch");
        assertEquals("ACME-PAYROLL-0314", entries.get(1).getReference());
    }
}
