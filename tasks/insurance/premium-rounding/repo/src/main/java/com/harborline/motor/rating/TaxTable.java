package com.harborline.motor.rating;

import java.math.BigDecimal;
import java.util.Map;

/** Insurance Premium Tax rates by tax region. */
public final class TaxTable {
    private static final Map<String, BigDecimal> RATES = Map.of(
            "GB", new BigDecimal("0.12"),
            "GB-JSY", new BigDecimal("0.00"),   // Jersey: no IPT
            "GB-GSY", new BigDecimal("0.00"),   // Guernsey: no IPT
            "IE", new BigDecimal("0.03"),
            "IM", new BigDecimal("0.12"));

    private TaxTable() {}

    public static BigDecimal rateFor(String region) {
        BigDecimal r = RATES.get(region);
        if (r == null) throw new IllegalArgumentException("unknown tax region " + region);
        return r;
    }
}
