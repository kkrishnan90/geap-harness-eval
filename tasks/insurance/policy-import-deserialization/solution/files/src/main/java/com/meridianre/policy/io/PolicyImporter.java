package com.meridianre.policy.io;

import com.meridianre.policy.model.PolicyBatch;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InvalidClassException;
import java.io.ObjectInputFilter;
import java.io.ObjectInputStream;
import java.util.Set;

/**
 * Reads a policy batch uploaded by brokers through the portal ("legacy batch upload").
 * The wire format is Java serialization of {@link PolicyBatch}, written by the
 * policy-admin system's exporter.
 *
 * <p>Uploads are untrusted: every stream gets its own allowlist filter with resource
 * limits, so no class outside the policy model can be instantiated (no gadget chains).
 */
public final class PolicyImporter {

    /** Upload size limit enforced by the portal gateway as well. */
    public static final int MAX_BLOB_BYTES = 20 * 1024 * 1024;
    public static final int MAX_DEPTH = 20;
    public static final int MAX_ARRAY_LENGTH = 10_000;
    public static final int MAX_REFERENCES = 1_000_000;

    static final Set<String> ALLOWED_CLASSES = Set.of(
            "com.meridianre.policy.model.PolicyBatch",
            "com.meridianre.policy.model.Policy",
            "com.meridianre.policy.model.Party",
            "com.meridianre.policy.model.Coverage",
            "com.meridianre.policy.model.PolicyStatus",
            "com.meridianre.policy.model.LineOfBusiness",
            "java.util.ArrayList",
            "java.math.BigDecimal",
            "java.math.BigInteger",
            "java.lang.Number",
            "java.lang.Enum",
            "java.time.Ser",
            "java.time.LocalDate");

    static final ObjectInputFilter FILTER = info -> {
        if (info.depth() > MAX_DEPTH || info.references() > MAX_REFERENCES
                || info.streamBytes() > MAX_BLOB_BYTES || info.arrayLength() > MAX_ARRAY_LENGTH) {
            return ObjectInputFilter.Status.REJECTED;
        }
        Class<?> cls = info.serialClass();
        if (cls == null) {
            return ObjectInputFilter.Status.UNDECIDED;
        }
        boolean array = cls.isArray();
        while (cls.isArray()) {
            cls = cls.getComponentType();
        }
        if (cls.isPrimitive() || (array && cls == Object.class) || ALLOWED_CLASSES.contains(cls.getName())) {
            return ObjectInputFilter.Status.ALLOWED;
        }
        return ObjectInputFilter.Status.REJECTED;
    };

    public PolicyBatch read(byte[] blob) throws ImportException {
        if (blob == null || blob.length == 0) {
            throw new ImportException("empty upload");
        }
        if (blob.length > MAX_BLOB_BYTES) {
            throw new ImportException("upload too large");
        }
        try (ObjectInputStream in = new ObjectInputStream(new ByteArrayInputStream(blob))) {
            in.setObjectInputFilter(FILTER);
            Object obj = in.readObject();
            if (!(obj instanceof PolicyBatch batch)) {
                throw new ImportException("not a policy batch: " + (obj == null ? "null" : obj.getClass().getName()));
            }
            return batch;
        } catch (InvalidClassException e) {
            throw new ImportException("rejected by deserialization filter", e);
        } catch (IOException | ClassNotFoundException e) {
            throw new ImportException("unreadable policy batch", e);
        }
    }
}
