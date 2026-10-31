package com.northbank.payments.pain.parser;

import com.northbank.payments.pain.model.CreditTransferTransaction;
import com.northbank.payments.pain.model.CustomerCreditTransferInitiation;
import com.northbank.payments.pain.model.GroupHeader;
import com.northbank.payments.pain.model.PaymentInformation;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;
import org.xml.sax.SAXException;

import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.List;

/**
 * DOM based parser for pain.001.001.09 CustomerCreditTransferInitiation messages.
 *
 * <p>Only the subset of elements the gateway needs is read; unknown elements are ignored.
 * Elements are matched by local name inside the pain.001 namespace.
 */
public final class Pain001Parser {
    public static final String NAMESPACE = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09";

    public CustomerCreditTransferInitiation parse(String xml) throws ParseException {
        return parse(new ByteArrayInputStream(xml.getBytes(StandardCharsets.UTF_8)));
    }

    public CustomerCreditTransferInitiation parse(InputStream in) throws ParseException {
        Document doc = readDocument(in);
        Element root = doc.getDocumentElement();
        if (!"Document".equals(root.getLocalName()) || !NAMESPACE.equals(root.getNamespaceURI())) {
            throw new ParseException("not a pain.001.001.09 Document: " + root.getNodeName());
        }
        Element cstmr = required(root, "CstmrCdtTrfInitn");
        GroupHeader header = parseGroupHeader(required(cstmr, "GrpHdr"));
        List<PaymentInformation> pmtInfs = new ArrayList<>();
        for (Element pmtInf : children(cstmr, "PmtInf")) {
            pmtInfs.add(parsePaymentInformation(pmtInf));
        }
        if (pmtInfs.isEmpty()) {
            throw new ParseException("missing mandatory element PmtInf");
        }
        return new CustomerCreditTransferInitiation(header, pmtInfs);
    }

    private Document readDocument(InputStream in) throws ParseException {
        try {
            DocumentBuilderFactory f = DocumentBuilderFactory.newInstance();
            f.setNamespaceAware(true);
            f.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            f.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            f.setXIncludeAware(false);
            f.setExpandEntityReferences(false);
            DocumentBuilder b = f.newDocumentBuilder();
            b.setErrorHandler(null);
            return b.parse(in);
        } catch (ParserConfigurationException e) {
            throw new IllegalStateException("XML parser not available", e);
        } catch (SAXException | IOException e) {
            throw new ParseException("malformed XML: " + e.getMessage(), e);
        }
    }

    private GroupHeader parseGroupHeader(Element grpHdr) throws ParseException {
        String msgId = text(required(grpHdr, "MsgId"));
        LocalDateTime created = parseDateTime(required(grpHdr, "CreDtTm"));
        int nbOfTxs = parseInt(required(grpHdr, "NbOfTxs"));
        Element ctrlSum = optional(grpHdr, "CtrlSum");
        Element initgPty = optional(grpHdr, "InitgPty");
        String initiator = initgPty == null ? null : optionalText(initgPty, "Nm");
        return new GroupHeader(msgId, created, nbOfTxs, ctrlSum == null ? null : parseAmount(ctrlSum), initiator);
    }

    private PaymentInformation parsePaymentInformation(Element pmtInf) throws ParseException {
        PaymentInformation.Builder b = PaymentInformation.builder()
                .paymentInformationId(text(required(pmtInf, "PmtInfId")))
                .paymentMethod(text(required(pmtInf, "PmtMtd")));
        Element btch = optional(pmtInf, "BtchBookg");
        if (btch != null) b.batchBooking(parseBoolean(btch));
        Element nb = optional(pmtInf, "NbOfTxs");
        if (nb != null) b.numberOfTransactions(parseInt(nb));
        Element cs = optional(pmtInf, "CtrlSum");
        if (cs != null) b.controlSum(parseAmount(cs));

        Element tp = optional(pmtInf, "PmtTpInf");
        if (tp != null) {
            Element svcLvl = optional(tp, "SvcLvl");
            if (svcLvl != null) b.serviceLevel(optionalText(svcLvl, "Cd"));
            Element lcl = optional(tp, "LclInstrm");
            if (lcl != null) b.localInstrument(optionalText(lcl, "Cd"));
        }

        Element reqd = required(pmtInf, "ReqdExctnDt");
        Element dt = optional(reqd, "Dt");
        b.requestedExecutionDate(parseDate(dt != null ? dt : reqd));

        b.debtorName(optionalText(required(pmtInf, "Dbtr"), "Nm"));
        b.debtorIban(text(required(required(required(pmtInf, "DbtrAcct"), "Id"), "IBAN")));
        Element dbtrAgt = optional(pmtInf, "DbtrAgt");
        if (dbtrAgt != null) {
            Element fin = optional(dbtrAgt, "FinInstnId");
            if (fin != null) b.debtorBic(optionalText(fin, "BICFI"));
        }

        List<Element> txs = children(pmtInf, "CdtTrfTxInf");
        if (txs.isEmpty()) {
            throw new ParseException("PmtInf " + text(required(pmtInf, "PmtInfId")) + ": missing mandatory element CdtTrfTxInf");
        }
        for (Element tx : txs) b.addTransaction(parseTransaction(tx));
        return b.build();
    }

    private CreditTransferTransaction parseTransaction(Element tx) throws ParseException {
        CreditTransferTransaction.Builder b = CreditTransferTransaction.builder();
        b.endToEndId(text(required(required(tx, "PmtId"), "EndToEndId")));
        Element instdAmt = required(required(tx, "Amt"), "InstdAmt");
        String ccy = instdAmt.getAttribute("Ccy");
        if (ccy == null || !ccy.matches("[A-Z]{3}")) {
            throw new ParseException("InstdAmt: missing or invalid Ccy attribute");
        }
        b.amount(parseAmount(instdAmt)).currency(ccy);
        Element cdtrAgt = optional(tx, "CdtrAgt");
        if (cdtrAgt != null) {
            Element fin = optional(cdtrAgt, "FinInstnId");
            if (fin != null) b.creditorBic(optionalText(fin, "BICFI"));
        }
        Element cdtr = optional(tx, "Cdtr");
        if (cdtr != null) b.creditorName(optionalText(cdtr, "Nm"));
        b.creditorIban(text(required(required(required(tx, "CdtrAcct"), "Id"), "IBAN")));
        Element rmt = optional(tx, "RmtInf");
        if (rmt != null) b.remittanceInfo(optionalText(rmt, "Ustrd"));
        return b.build();
    }

    // ---- DOM helpers -------------------------------------------------------------------

    static List<Element> children(Element parent, String localName) {
        List<Element> out = new ArrayList<>();
        NodeList nl = parent.getChildNodes();
        for (int i = 0; i < nl.getLength(); i++) {
            Node n = nl.item(i);
            if (n.getNodeType() == Node.ELEMENT_NODE && localName.equals(n.getLocalName())
                    && NAMESPACE.equals(n.getNamespaceURI())) {
                out.add((Element) n);
            }
        }
        return out;
    }

    static Element optional(Element parent, String localName) throws ParseException {
        List<Element> l = children(parent, localName);
        if (l.size() > 1) {
            throw new ParseException(parent.getLocalName() + ": element " + localName + " must not repeat");
        }
        return l.isEmpty() ? null : l.get(0);
    }

    static Element required(Element parent, String localName) throws ParseException {
        Element e = optional(parent, localName);
        if (e == null) {
            throw new ParseException(parent.getLocalName() + ": missing mandatory element " + localName);
        }
        return e;
    }

    static String text(Element e) {
        return e.getTextContent().trim();
    }

    static String optionalText(Element parent, String localName) throws ParseException {
        Element e = optional(parent, localName);
        return e == null ? null : text(e);
    }

    private static int parseInt(Element e) throws ParseException {
        try {
            return Integer.parseInt(text(e));
        } catch (NumberFormatException ex) {
            throw new ParseException(e.getLocalName() + ": not a number: " + text(e));
        }
    }

    private static boolean parseBoolean(Element e) throws ParseException {
        String s = text(e);
        switch (s) {
            case "true": case "1": return true;
            case "false": case "0": return false;
            default: throw new ParseException(e.getLocalName() + ": invalid boolean: " + s);
        }
    }

    private static BigDecimal parseAmount(Element e) throws ParseException {
        String s = text(e);
        if (!s.matches("[0-9]{1,18}(\\.[0-9]{1,5})?")) {
            throw new ParseException(e.getLocalName() + ": invalid amount: " + s);
        }
        return new BigDecimal(s);
    }

    private static LocalDate parseDate(Element e) throws ParseException {
        try {
            return LocalDate.parse(text(e));
        } catch (DateTimeParseException ex) {
            throw new ParseException(e.getLocalName() + ": invalid date: " + text(e));
        }
    }

    private static LocalDateTime parseDateTime(Element e) throws ParseException {
        String s = text(e);
        try {
            return LocalDateTime.parse(s);
        } catch (DateTimeParseException ex) {
            try {
                return OffsetDateTime.parse(s).toLocalDateTime();
            } catch (DateTimeParseException ex2) {
                throw new ParseException(e.getLocalName() + ": invalid date-time: " + s);
            }
        }
    }
}
