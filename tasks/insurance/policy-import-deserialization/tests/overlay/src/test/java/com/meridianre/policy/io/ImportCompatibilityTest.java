package com.meridianre.policy.io;

import com.meridianre.policy.model.Coverage;
import com.meridianre.policy.model.LineOfBusiness;
import com.meridianre.policy.model.Party;
import com.meridianre.policy.model.Policy;
import com.meridianre.policy.model.PolicyBatch;
import com.meridianre.policy.model.PolicyStatus;
import testkit.Test;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InvalidClassException;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.PriorityQueue;
import java.util.concurrent.atomic.AtomicInteger;

import static testkit.Assert.*;

public class ImportCompatibilityTest {
    static Policy policy(String number, LineOfBusiness line, PolicyStatus status) {
        Party holder = new Party("P-" + number, "Holder of " + number, "DE");
        return new Policy(number, line, holder, LocalDate.of(2026, 1, 1), LocalDate.of(2027, 1, 1), "EUR", status,
                List.of(new Coverage("FIRE", new BigDecimal("1000000.00"), new BigDecimal("5000.00"), new BigDecimal("0.0012")),
                        new Coverage("FLOOD", new BigDecimal("250000.00"), new BigDecimal("10000.00"), new BigDecimal("0.0040"))));
    }
    static PolicyBatch batch(int n) {
        List<Policy> list = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            list.add(policy(String.format("PR-2026-%06d", i + 1), LineOfBusiness.PROPERTY, PolicyStatus.BOUND));
        }
        return new PolicyBatch("B-20260301-01", "PAS-LEGACY", list);
    }

    @Test
    public void allEnumValuesAndLinesRoundTrip() throws Exception {
        List<Policy> list = new ArrayList<>();
        int i = 0;
        for (LineOfBusiness line : LineOfBusiness.values()) {
            for (PolicyStatus st : PolicyStatus.values()) {
                list.add(policy(String.format("XX-2026-%06d", ++i), line, st));
            }
        }
        PolicyBatch back = new PolicyImporter().read(new PolicyExporter().export(new PolicyBatch("B", "PAS", list)));
        assertEquals(list, back.policies());
    }

    @Test
    public void largestAllowedBatchImports() throws Exception {
        PolicyBatch b = batch(10_000);
        PolicyBatch back = new PolicyImporter().read(new PolicyExporter().export(b));
        assertEquals(10_000, back.policies().size());
        assertEquals("PR-2026-010000", back.policies().get(9_999).policyNumber());
    }

    @Test
    public void unusualAmountsAndNamesSurvive() throws Exception {
        Policy p = new Policy("MA-2026-000001", LineOfBusiness.MARINE, new Party("P-9", "Société Générale d'Assurances Ωmega", null),
                LocalDate.of(2026, 2, 28), LocalDate.of(2028, 2, 29), "CHF", PolicyStatus.IN_FORCE,
                List.of(new Coverage("HULL", new BigDecimal("123456789012345678901234567890.123456"), BigDecimal.ZERO,
                        new BigDecimal("1E-9"))));
        PolicyBatch back = new PolicyImporter().read(new PolicyExporter().export(new PolicyBatch("B", "PAS", List.of(p))));
        assertEquals(p, back.policies().get(0));
    }

    @Test
    public void noJvmWideFilterInstalled() throws Exception {
        new PolicyImporter().read(new PolicyExporter().export(batch(1)));
        assertNull(java.io.ObjectInputFilter.Config.getSerialFilter(), "global serial filter");
        HashMap<String, Integer> m = new HashMap<>();
        m.put("a", 1);
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) {
            out.writeObject(m);
        }
        try (ObjectInputStream in = new ObjectInputStream(new java.io.ByteArrayInputStream(bytes.toByteArray()))) {
            assertEquals(m, in.readObject());
        }
    }

    @Test
    public void wrongTopLevelTypeStillImportException() throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) {
            out.writeObject("just a string");
        }
        assertThrows(ImportException.class, () -> new PolicyImporter().read(bytes.toByteArray()));
    }
}
