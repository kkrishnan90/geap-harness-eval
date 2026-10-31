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

public class PolicyImportLimitsTest {
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

    static byte[] serialize(Object o) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) {
            out.writeObject(o);
        }
        return bytes.toByteArray();
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    static PolicyBatch batchSmuggling(Object payload) {
        PolicyBatch b = batch(1);
        ((List) b.policies().get(0).coverages()).add(payload);
        return b;
    }

    static void rejected(byte[] blob) {
        ImportException e = assertThrows(ImportException.class, () -> new PolicyImporter().read(blob));
        assertTrue(e.getCause() instanceof InvalidClassException,
                "cause must be the filter's InvalidClassException, was " + e.getCause());
    }

    @Test
    public void deeplyNestedGraphRejected() throws Exception {
        // only allowed classes, but nested ~40 levels deep (limit is 20)
        ArrayList<Object> outer = new ArrayList<>();
        ArrayList<Object> cur = outer;
        for (int i = 0; i < 40; i++) {
            ArrayList<Object> next = new ArrayList<>();
            cur.add(next);
            cur = next;
        }
        rejected(serialize(batchSmuggling(outer)));
    }

    @Test
    public void oversizedCollectionRejected() throws Exception {
        // 10,001 policies: one more than the documented batch limit (stream is small: shared objects)
        Policy p = batch(1).policies().get(0);
        List<Policy> many = new ArrayList<>();
        for (int i = 0; i < 10_001; i++) many.add(p);
        rejected(serialize(new PolicyBatch("B-BIG", "PAS", many)));
    }

    @Test
    public void oversizedNestedCollectionRejected() throws Exception {
        Coverage c = batch(1).policies().get(0).coverages().get(0);
        ArrayList<Object> covs = new ArrayList<>();
        for (int i = 0; i < 20_000; i++) covs.add(c);
        rejected(serialize(batchSmuggling(covs)));
    }
}
