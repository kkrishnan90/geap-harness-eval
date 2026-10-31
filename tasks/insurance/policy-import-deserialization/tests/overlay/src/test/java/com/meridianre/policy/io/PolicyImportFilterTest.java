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

public class PolicyImportFilterTest {
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

    /** Stand-in for a gadget class: any code in readObject would run during deserialization. */
    public static final class Gadget implements Serializable {
        private static final long serialVersionUID = 1L;
        static final AtomicInteger READS = new AtomicInteger();
        String command = "touch /tmp/pwned";

        private void readObject(ObjectInputStream in) throws IOException, ClassNotFoundException {
            in.defaultReadObject();
            READS.incrementAndGet();
        }
    }

    /** A subclass of an allowed container type that smuggles code into readObject. */
    public static final class EvilList<E> extends ArrayList<E> {
        private static final long serialVersionUID = 1L;
        static final AtomicInteger READS = new AtomicInteger();

        private void readObject(ObjectInputStream in) throws IOException, ClassNotFoundException {
            in.defaultReadObject();
            READS.incrementAndGet();
        }
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
        PolicyBatch b = batch(2);
        ((List) b.policies().get(1).coverages()).add(payload);
        return b;
    }

    static ImportException rejected(byte[] blob) {
        ImportException e = assertThrows(ImportException.class, () -> new PolicyImporter().read(blob));
        assertTrue(e.getCause() instanceof InvalidClassException,
                "cause must be the filter's InvalidClassException, was " + e.getCause());
        return e;
    }

    @Test
    public void topLevelGadgetRejectedBeforeReadObject() throws Exception {
        int before = Gadget.READS.get();
        rejected(serialize(new Gadget()));
        assertEquals(before, Gadget.READS.get(), "Gadget.readObject must not run");
    }

    @Test
    public void nestedGadgetRejectedBeforeReadObject() throws Exception {
        int before = Gadget.READS.get();
        rejected(serialize(batchSmuggling(new Gadget())));
        assertEquals(before, Gadget.READS.get(), "Gadget.readObject must not run");
    }

    @Test
    public void subclassOfAllowedContainerRejected() throws Exception {
        int before = EvilList.READS.get();
        EvilList<Policy> evil = new EvilList<>();
        evil.addAll(batch(1).policies());
        rejected(serialize(batchSmuggling(evil)));
        assertEquals(before, EvilList.READS.get(), "EvilList.readObject must not run");
    }

    @Test
    public void jdkCollectionsOutsideAllowlistRejected() throws Exception {
        HashMap<String, Object> map = new HashMap<>();
        map.put("k", "v");
        rejected(serialize(batchSmuggling(map)));
        PriorityQueue<String> pq = new PriorityQueue<>();
        pq.add("a");
        rejected(serialize(batchSmuggling(pq)));
    }

    @Test
    public void topLevelJdkObjectRejectedByFilter() throws Exception {
        rejected(serialize(new HashMap<String, String>()));
        rejected(serialize(new java.util.Date(0)));
    }
}
