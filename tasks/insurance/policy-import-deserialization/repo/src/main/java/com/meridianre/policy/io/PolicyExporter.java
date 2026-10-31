package com.meridianre.policy.io;

import com.meridianre.policy.model.PolicyBatch;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.ObjectOutputStream;
import java.io.UncheckedIOException;

/** Writes batches in the legacy wire format (used by the DR replication job and tests). */
public final class PolicyExporter {
    public byte[] export(PolicyBatch batch) {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) {
            out.writeObject(batch);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        return bytes.toByteArray();
    }
}
