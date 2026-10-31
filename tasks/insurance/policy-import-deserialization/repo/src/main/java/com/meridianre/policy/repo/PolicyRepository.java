package com.meridianre.policy.repo;

import com.meridianre.policy.model.Policy;

import java.util.Collection;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

/** In-memory stand-in for the policy store (the Oracle adapter lives in policy-admin-db). */
public final class PolicyRepository {
    private final Map<String, Policy> byNumber = new LinkedHashMap<>();

    public synchronized void upsert(Policy p) { byNumber.put(p.policyNumber(), p); }

    public synchronized Optional<Policy> find(String number) { return Optional.ofNullable(byNumber.get(number)); }

    public synchronized int size() { return byNumber.size(); }

    public synchronized Collection<Policy> all() { return Collections.unmodifiableCollection(new java.util.ArrayList<>(byNumber.values())); }
}
