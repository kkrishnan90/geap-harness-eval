package com.meridianre.policy.model;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.List;

/** Unit of transfer from the legacy policy-admin system: one nightly batch. */
public final class PolicyBatch implements Serializable {
    private static final long serialVersionUID = 2L;

    private final String batchId;
    private final String sourceSystem;
    private final ArrayList<Policy> policies;

    public PolicyBatch(String batchId, String sourceSystem, List<Policy> policies) {
        this.batchId = batchId;
        this.sourceSystem = sourceSystem;
        this.policies = new ArrayList<>(policies);
    }

    public String batchId() { return batchId; }
    public String sourceSystem() { return sourceSystem; }
    public List<Policy> policies() { return policies; }
}
