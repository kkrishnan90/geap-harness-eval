package com.meridianre.policy.io;

import com.meridianre.policy.model.Coverage;
import com.meridianre.policy.model.LineOfBusiness;
import com.meridianre.policy.model.Party;
import com.meridianre.policy.model.Policy;
import com.meridianre.policy.model.PolicyBatch;
import com.meridianre.policy.model.PolicyStatus;
import testkit.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

import static testkit.Assert.*;

public class PolicyRoundTripTest {
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
    public void exportThenImportIsLossless() throws Exception {
        PolicyBatch b = batch(3);
        PolicyBatch back = new PolicyImporter().read(new PolicyExporter().export(b));
        assertEquals("B-20260301-01", back.batchId());
        assertEquals(b.policies(), back.policies());
    }

    @Test
    public void emptyUploadRejected() {
        assertThrows(ImportException.class, () -> new PolicyImporter().read(new byte[0]));
        assertThrows(ImportException.class, () -> new PolicyImporter().read(null));
    }

    @Test
    public void garbageRejected() {
        assertThrows(ImportException.class, () -> new PolicyImporter().read("PK\u0003\u0004 not a stream".getBytes()));
    }

    @Test
    public void truncatedStreamRejected() {
        byte[] full = new PolicyExporter().export(batch(2));
        byte[] cut = java.util.Arrays.copyOf(full, full.length / 2);
        assertThrows(ImportException.class, () -> new PolicyImporter().read(cut));
    }

    @Test
    public void oversizedUploadRejected() {
        assertThrows(ImportException.class, () -> new PolicyImporter().read(new byte[PolicyImporter.MAX_BLOB_BYTES + 1]));
    }
}
