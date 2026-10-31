package com.harborline.motor.rating;

import java.math.BigDecimal;
import java.util.List;
import java.util.Objects;

/** Input to {@link PremiumCalculator}. */
public final class RatingRequest {
    private final BigDecimal baseRate;
    private final List<BigDecimal> factors;
    private final BigDecimal minimumPremium;
    private final String taxRegion;
    private final int instalments;

    public RatingRequest(BigDecimal baseRate, List<BigDecimal> factors, BigDecimal minimumPremium,
                         String taxRegion, int instalments) {
        this.baseRate = Objects.requireNonNull(baseRate, "baseRate");
        this.factors = List.copyOf(factors);
        this.minimumPremium = Objects.requireNonNull(minimumPremium, "minimumPremium");
        this.taxRegion = Objects.requireNonNull(taxRegion, "taxRegion");
        if (instalments < 1 || instalments > 12) {
            throw new IllegalArgumentException("instalments must be 1..12: " + instalments);
        }
        this.instalments = instalments;
    }

    public BigDecimal baseRate() { return baseRate; }
    public List<BigDecimal> factors() { return factors; }
    public BigDecimal minimumPremium() { return minimumPremium; }
    public String taxRegion() { return taxRegion; }
    public int instalments() { return instalments; }
}
