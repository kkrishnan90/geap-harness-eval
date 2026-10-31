package com.meridianre.policy.service;

import com.meridianre.policy.io.PolicyImporter;
import com.meridianre.policy.repo.PolicyRepository;
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

public class ImportServiceSecurityTest {
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

    public static final class Beacon implements Serializable {
        private static final long serialVersionUID = 1L;
        static final AtomicInteger READS = new AtomicInteger();

        private void readObject(ObjectInputStream in) throws IOException, ClassNotFoundException {
            in.defaultReadObject();
            READS.incrementAndGet();
        }
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    @Test
    public void maliciousUploadRejectedWithoutSideEffects() throws Exception {
        PolicyBatch b = batch(3);
        ((List) b.policies().get(2).coverages()).add(new Beacon());
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) {
            out.writeObject(b);
        }
        PolicyRepository repo = new PolicyRepository();
        ImportService s = new ImportService(new PolicyImporter(), new PolicyValidator(), repo);
        int before = Beacon.READS.get();
        ImportReport r = s.upload("broker-666", bytes.toByteArray());
        assertFalse(r.accepted(), "upload must be rejected");
        assertEquals(0, repo.size());
        assertEquals(before, Beacon.READS.get(), "Beacon.readObject must not run");
        assertTrue(s.auditLog().get(0).startsWith("broker-666 REJECTED"), "audit: " + s.auditLog());
        assertTrue(r.error() != null && !r.error().contains("Beacon"), "error must not echo class names: " + r.error());
    }
}
