package com.northbank.payments.pain;

import com.northbank.payments.pain.model.CustomerCreditTransferInitiation;
import com.northbank.payments.pain.parser.Pain001Parser;
import com.northbank.payments.pain.validation.IssueCode;
import com.northbank.payments.pain.validation.PaymentValidator;
import com.northbank.payments.pain.validation.ValidationIssue;
import testkit.Test;

import java.io.FileInputStream;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.List;

import static testkit.Assert.*;

public class PaymentValidatorTest {
    static final LocalDate PROCESSING = LocalDate.of(2025, 3, 14);

    static String fixtureXml() throws Exception {
        return Files.readString(Path.of("src/test/resources/pain001/two-batches.xml"));
    }

    static List<ValidationIssue> validate(String xml) throws Exception {
        CustomerCreditTransferInitiation m = new Pain001Parser().parse(xml);
        return new PaymentValidator(PROCESSING).validate(m);
    }

    static boolean has(List<ValidationIssue> issues, IssueCode code) {
        return issues.stream().anyMatch(i -> i.getCode() == code);
    }

    @Test
    public void cleanFileHasNoIssues() throws Exception {
        List<ValidationIssue> issues = validate(fixtureXml());
        assertTrue(issues.isEmpty(), issues.toString());
    }

    @Test
    public void groupHeaderCountMismatch() throws Exception {
        List<ValidationIssue> issues = validate(fixtureXml().replace("<NbOfTxs>3</NbOfTxs>", "<NbOfTxs>4</NbOfTxs>"));
        assertTrue(has(issues, IssueCode.GRPHDR_NB_OF_TXS_MISMATCH), issues.toString());
    }

    @Test
    public void paymentInformationControlSumMismatch() throws Exception {
        List<ValidationIssue> issues = validate(fixtureXml().replace("<CtrlSum>3100.75</CtrlSum>", "<CtrlSum>3100.70</CtrlSum>"));
        assertEquals(1, issues.size(), issues.toString());
        assertEquals(IssueCode.PMTINF_CTRL_SUM_MISMATCH, issues.get(0).getCode());
        assertEquals("ACME-SUPPLIERS-0314", issues.get(0).getPaymentInformationId());
    }

    @Test
    public void duplicateEndToEndId() throws Exception {
        List<ValidationIssue> issues = validate(fixtureXml().replace("SAL-0314-0001", "INV-2025-0412"));
        assertTrue(has(issues, IssueCode.DUPLICATE_END_TO_END_ID), issues.toString());
    }

    @Test
    public void amountWithThreeDecimals() throws Exception {
        String xml = fixtureXml().replace(">1250.00<", ">1250.001<").replace("<CtrlSum>1250.00</CtrlSum>", "<CtrlSum>1250.001</CtrlSum>")
                .replace("<CtrlSum>4350.75</CtrlSum>", "<CtrlSum>4350.751</CtrlSum>");
        List<ValidationIssue> issues = validate(xml);
        assertEquals(1, issues.size(), issues.toString());
        assertEquals(IssueCode.INVALID_AMOUNT, issues.get(0).getCode());
        assertEquals("SAL-0314-0001", issues.get(0).getEndToEndId());
    }

    @Test
    public void executionDateInPast() throws Exception {
        List<ValidationIssue> issues = validate(fixtureXml().replace("2025-03-17", "2025-03-13"));
        assertTrue(has(issues, IssueCode.EXECUTION_DATE_IN_PAST), issues.toString());
        assertTrue(PaymentValidator.hasErrors(issues));
    }

    @Test
    public void missingCreditorNameIsWarningOnly() throws Exception {
        List<ValidationIssue> issues = validate(fixtureXml().replace("<Cdtr><Nm>J. Novak</Nm></Cdtr>", ""));
        assertTrue(has(issues, IssueCode.MISSING_CREDITOR_NAME), issues.toString());
        assertFalse(PaymentValidator.hasErrors(issues));
    }
}
