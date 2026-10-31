package com.northbank.payments.pain;

import com.northbank.payments.pain.model.PaymentInformation;
import com.northbank.payments.pain.parser.Pain001Parser;
import com.northbank.payments.pain.validation.IssueCode;
import com.northbank.payments.pain.validation.PaymentValidator;
import com.northbank.payments.pain.validation.Severity;
import com.northbank.payments.pain.validation.ValidationIssue;
import testkit.Test;

import java.time.LocalDate;
import java.util.List;
import java.util.stream.Collectors;

import static testkit.Assert.*;

public class BatchBookingValidationTest {
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

    static List<ValidationIssue> validate(String xml) throws Exception {
        return new PaymentValidator(LocalDate.of(2025, 3, 14)).validate(new Pain001Parser().parse(xml));
    }

    static List<IssueCode> codes(List<ValidationIssue> issues) {
        return issues.stream().map(ValidationIssue::getCode).collect(Collectors.toList());
    }

    @Test
    public void newCodesAreErrors() {
        assertEquals(Severity.ERROR, IssueCode.valueOf("BATCH_BOOKING_NOT_ALLOWED").getSeverity());
        assertEquals(Severity.ERROR, IssueCode.valueOf("BATCH_CTRL_SUM_MISSING").getSeverity());
        assertEquals(Severity.ERROR, IssueCode.valueOf("BATCH_MIXED_CURRENCY").getSeverity());
    }

    @Test
    public void batchWithoutControlSum() throws Exception {
        List<ValidationIssue> issues = validate(msg("true", null, null, null, "E1", "10.00", "EUR", "E2", "5.00", "EUR"));
        assertEquals(List.of(IssueCode.BATCH_CTRL_SUM_MISSING), codes(issues));
        assertEquals("PI-BATCH-01", issues.get(0).getPaymentInformationId());
        assertNull(issues.get(0).getEndToEndId(), "endToEndId");
    }

    @Test
    public void implicitBatchWithoutControlSum() throws Exception {
        List<ValidationIssue> issues = validate(msg(null, null, "SEPA", null, "E1", "10.00", "EUR"));
        assertEquals(List.of(IssueCode.BATCH_CTRL_SUM_MISSING), codes(issues));
    }

    @Test
    public void batchWithMixedCurrencies() throws Exception {
        List<ValidationIssue> issues = validate(msg("true", "15.00", null, null,
                "E1", "10.00", "EUR", "E2", "3.00", "CHF", "E3", "2.00", "CHF"));
        assertEquals(List.of(IssueCode.BATCH_MIXED_CURRENCY), codes(issues));
        assertTrue(PaymentValidator.hasErrors(issues));
    }

    @Test
    public void batchMissingSumAndMixedCurrencyBothReported() throws Exception {
        List<IssueCode> c = codes(validate(msg(null, null, null, null, "E1", "10.00", "EUR", "E2", "3.00", "USD")));
        assertEquals(2, c.size(), c.toString());
        assertTrue(c.contains(IssueCode.BATCH_CTRL_SUM_MISSING) && c.contains(IssueCode.BATCH_MIXED_CURRENCY), c.toString());
    }

    @Test
    public void singleBookingAllowsMixedCurrencyAndNoSum() throws Exception {
        List<ValidationIssue> issues = validate(msg("false", null, null, null, "E1", "10.00", "EUR", "E2", "3.00", "USD"));
        assertTrue(issues.isEmpty(), issues.toString());
    }

    @Test
    public void explicitBatchForUrgentNotAllowed() throws Exception {
        List<ValidationIssue> issues = validate(msg("true", "10.00", "URGP", null, "E1", "10.00", "EUR"));
        assertEquals(List.of(IssueCode.BATCH_BOOKING_NOT_ALLOWED), codes(issues));
        assertEquals("PI-BATCH-01", issues.get(0).getPaymentInformationId());
    }

    @Test
    public void explicitBatchForInstantNotAllowedAndSuppressesOtherBatchRules() throws Exception {
        List<ValidationIssue> issues = validate(msg("1", null, "SEPA", "INST", "E1", "10.00", "EUR", "E2", "1.00", "USD"));
        assertEquals(List.of(IssueCode.BATCH_BOOKING_NOT_ALLOWED), codes(issues));
    }

    @Test
    public void batchRulesComeBeforeTransactionIssues() throws Exception {
        List<ValidationIssue> issues = validate(msg("true", null, null, null, "E1", "10.001", "EUR"));
        assertEquals(List.of(IssueCode.BATCH_CTRL_SUM_MISSING, IssueCode.INVALID_AMOUNT), codes(issues));
    }

    @Test
    public void existingControlSumCheckStillApplies() throws Exception {
        List<IssueCode> c = codes(validate(msg("true", "11.00", null, null, "E1", "10.00", "EUR")));
        assertEquals(List.of(IssueCode.PMTINF_CTRL_SUM_MISMATCH), c);
    }
}
