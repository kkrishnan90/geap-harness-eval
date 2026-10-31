package com.harborline.motor.policy;

import java.time.LocalDate;
import java.util.Objects;

/** A private motor policy as held in the policy administration system. */
public final class Policy {
    public enum Cover { COMPREHENSIVE, THIRD_PARTY_FIRE_THEFT, THIRD_PARTY_ONLY }

    private final String policyNumber;
    private final String vehicleRegistration;
    private final Cover cover;
    private final LocalDate inception;
    private final LocalDate expiry;

    public Policy(String policyNumber, String vehicleRegistration, Cover cover, LocalDate inception, LocalDate expiry) {
        this.policyNumber = Objects.requireNonNull(policyNumber);
        this.vehicleRegistration = Objects.requireNonNull(vehicleRegistration);
        this.cover = Objects.requireNonNull(cover);
        if (!expiry.isAfter(inception)) throw new IllegalArgumentException("expiry must be after inception");
        this.inception = inception;
        this.expiry = expiry;
    }

    public String policyNumber() { return policyNumber; }
    public String vehicleRegistration() { return vehicleRegistration; }
    public Cover cover() { return cover; }
    public LocalDate inception() { return inception; }
    public LocalDate expiry() { return expiry; }

    public boolean isInForce(LocalDate date) {
        return !date.isBefore(inception) && date.isBefore(expiry);
    }
}
