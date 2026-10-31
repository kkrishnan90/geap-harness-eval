package com.meridianre.policy.io;

import com.meridianre.policy.model.PolicyBatch;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.ObjectInputStream;

/**
 * Reads a policy batch uploaded by brokers through the portal ("legacy batch upload").
 * The wire format is Java serialization of {@link PolicyBatch}, written by the
 * policy-admin system's exporter.
 */
public final class PolicyImporter {

    /** Upload size limit enforced by the portal gateway as well. */
    public static final int MAX_BLOB_BYTES = 20 * 1024 * 1024;

    public PolicyBatch read(byte[] blob) throws ImportException {
        if (blob == null || blob.length == 0) {
            throw new ImportException("empty upload");
        }
        if (blob.length > MAX_BLOB_BYTES) {
            throw new ImportException("upload too large");
        }
        try (ObjectInputStream in = new ObjectInputStream(new ByteArrayInputStream(blob))) {
            Object obj = in.readObject();
            if (!(obj instanceof PolicyBatch batch)) {
                throw new ImportException("not a policy batch: " + (obj == null ? "null" : obj.getClass().getName()));
            }
            return batch;
        } catch (IOException | ClassNotFoundException e) {
            throw new ImportException("unreadable policy batch", e);
        }
    }
}
