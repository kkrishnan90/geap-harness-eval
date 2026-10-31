package com.harborline.motor.rating;

import java.math.BigDecimal;
import java.util.List;

/** Result of a rating: what goes on the policy schedule. */
public final class PremiumBreakdown {
    private final BigDecimal netPremium;
    private final BigDecimal tax;
    private final BigDecimal grossPremium;
    private final List<BigDecimal> instalments;

    public PremiumBreakdown(BigDecimal netPremium, BigDecimal tax, BigDecimal grossPremium,
                            List<BigDecimal> instalments) {
        this.netPremium = netPremium;
        this.tax = tax;
        this.grossPremium = grossPremium;
        this.instalments = List.copyOf(instalments);
    }

    public BigDecimal netPremium() { return netPremium; }
    public BigDecimal tax() { return tax; }
    public BigDecimal grossPremium() { return grossPremium; }
    /** Instalment amounts in collection order (first collection first). */
    public List<BigDecimal> instalments() { return instalments; }

    @Override
    public String toString() {
        return "PremiumBreakdown{net=" + netPremium + ", tax=" + tax + ", gross=" + grossPremium
                + ", instalments=" + instalments + "}";
    }
}
