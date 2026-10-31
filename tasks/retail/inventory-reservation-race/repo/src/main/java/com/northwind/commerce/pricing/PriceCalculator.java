package com.northwind.commerce.pricing;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Map;

/** Line and basket totals. Prices are tax-inclusive (EU B2C); VAT is extracted per tax class. */
public class PriceCalculator {
    private static final Map<String, BigDecimal> VAT = Map.of(
        "standard", new BigDecimal("0.20"),
        "reduced", new BigDecimal("0.05"),
        "zero", BigDecimal.ZERO);

    public BigDecimal lineTotal(BigDecimal unitPrice, int quantity) {
        return unitPrice.multiply(BigDecimal.valueOf(quantity)).setScale(2, RoundingMode.HALF_UP);
    }

    /** VAT contained in a gross amount: gross * rate / (1 + rate). */
    public BigDecimal includedVat(BigDecimal gross, String taxClass) {
        BigDecimal rate = VAT.get(taxClass);
        if (rate == null) throw new IllegalArgumentException("unknown tax class " + taxClass);
        return gross.multiply(rate).divide(BigDecimal.ONE.add(rate), 2, RoundingMode.HALF_UP);
    }
}
