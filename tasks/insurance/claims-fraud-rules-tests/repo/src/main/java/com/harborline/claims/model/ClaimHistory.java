package com.harborline.claims.model;

import java.util.List;

/** Prior claims relevant for fraud screening (all claimants, all policies). */
public final class ClaimHistory {
    private final List<PriorClaim> claims;

    public ClaimHistory(List<PriorClaim> claims) { this.claims = List.copyOf(claims); }

    public static ClaimHistory empty() { return new ClaimHistory(List.of()); }

    public List<PriorClaim> claims() { return claims; }
}
