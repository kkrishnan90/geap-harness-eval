package com.meridianre.policy.model;

import java.io.Serializable;
import java.util.Objects;

/** Policyholder or broker reference. */
public final class Party implements Serializable {
    private static final long serialVersionUID = 3L;

    private final String partyId;
    private final String name;
    private final String countryCode;

    public Party(String partyId, String name, String countryCode) {
        this.partyId = partyId;
        this.name = name;
        this.countryCode = countryCode;
    }

    public String partyId() { return partyId; }
    public String name() { return name; }
    public String countryCode() { return countryCode; }

    @Override public boolean equals(Object o) {
        return o instanceof Party p && partyId.equals(p.partyId) && name.equals(p.name)
                && Objects.equals(countryCode, p.countryCode);
    }
    @Override public int hashCode() { return Objects.hash(partyId, name, countryCode); }
    @Override public String toString() { return "Party[" + partyId + "]"; }
}
