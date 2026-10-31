package com.meridianre.policy.model;

import java.io.Serializable;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/** A policy as exchanged with the legacy policy-admin system (Java serialization, v4 layout). */
public final class Policy implements Serializable {
    private static final long serialVersionUID = 4L;

    private final String policyNumber;
    private final LineOfBusiness line;
    private final Party holder;
    private final LocalDate inception;
    private final LocalDate expiry;
    private final String currency;
    private final PolicyStatus status;
    private final ArrayList<Coverage> coverages;

    public Policy(String policyNumber, LineOfBusiness line, Party holder, LocalDate inception, LocalDate expiry,
                  String currency, PolicyStatus status, List<Coverage> coverages) {
        this.policyNumber = policyNumber;
        this.line = line;
        this.holder = holder;
        this.inception = inception;
        this.expiry = expiry;
        this.currency = currency;
        this.status = status;
        this.coverages = new ArrayList<>(coverages);
    }

    public String policyNumber() { return policyNumber; }
    public LineOfBusiness line() { return line; }
    public Party holder() { return holder; }
    public LocalDate inception() { return inception; }
    public LocalDate expiry() { return expiry; }
    public String currency() { return currency; }
    public PolicyStatus status() { return status; }
    public List<Coverage> coverages() { return coverages; }

    @Override public boolean equals(Object o) {
        return o instanceof Policy p && policyNumber.equals(p.policyNumber) && line == p.line
                && holder.equals(p.holder) && inception.equals(p.inception) && expiry.equals(p.expiry)
                && currency.equals(p.currency) && status == p.status && coverages.equals(p.coverages);
    }
    @Override public int hashCode() { return Objects.hash(policyNumber, line, inception); }
    @Override public String toString() { return "Policy[" + policyNumber + "]"; }
}
