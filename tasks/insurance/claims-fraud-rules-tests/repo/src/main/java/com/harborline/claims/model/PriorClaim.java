package com.harborline.claims.model;

import java.time.LocalDate;
import java.util.Objects;

/** A previously registered claim (any policy) from the claims data warehouse. */
public final class PriorClaim {
    private final String claimId;
    private final String claimantId;
    private final LocalDate lossDate;
    private final String payoutIban;

    public PriorClaim(String claimId, String claimantId, LocalDate lossDate, String payoutIban) {
        this.claimId = Objects.requireNonNull(claimId);
        this.claimantId = Objects.requireNonNull(claimantId);
        this.lossDate = Objects.requireNonNull(lossDate);
        this.payoutIban = Objects.requireNonNull(payoutIban);
    }

    public String claimId() { return claimId; }
    public String claimantId() { return claimantId; }
    public LocalDate lossDate() { return lossDate; }
    public String payoutIban() { return payoutIban; }
}
