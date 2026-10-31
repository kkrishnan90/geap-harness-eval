package com.harborline.motor.rating;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.List;

/**
 * Computes the premium for a motor policy.
 *
 * <p>Rounding policy (pricing handbook, section 4.2):
 * <ol>
 *   <li>The net premium is base rate multiplied by every rating factor, computed at full
 *       precision and rounded <b>once</b> to pence using banker's rounding (HALF_EVEN).</li>
 *   <li>The minimum premium is applied to the rounded net premium.</li>
 *   <li>Insurance Premium Tax is the rounded net premium multiplied by the region's rate,
 *       rounded to pence with HALF_EVEN.</li>
 *   <li>Gross premium = net premium + tax.</li>
 *   <li>Instalments: gross / n rounded <b>down</b> to pence; the pence left over are added
 *       to the first instalment, so the instalments always sum exactly to the gross premium.</li>
 * </ol>
 */
public final class PremiumCalculator {

    private static final int PENCE = 2;

    public PremiumBreakdown calculate(RatingRequest request) {
        BigDecimal net = request.baseRate();
        for (BigDecimal factor : request.factors()) {
            net = net.multiply(factor);
        }
        net = net.setScale(PENCE, RoundingMode.HALF_EVEN);
        if (net.compareTo(request.minimumPremium()) < 0) {
            net = request.minimumPremium().setScale(PENCE, RoundingMode.HALF_EVEN);
        }

        BigDecimal tax = net.multiply(TaxTable.rateFor(request.taxRegion())).setScale(PENCE, RoundingMode.HALF_EVEN);

        BigDecimal gross = net.add(tax);
        return new PremiumBreakdown(net, tax, gross, split(gross, request.instalments()));
    }

    /** Splits an amount into {@code n} collections. */
    public static List<BigDecimal> split(BigDecimal amount, int n) {
        BigDecimal total = amount.setScale(PENCE, RoundingMode.UNNECESSARY);
        BigDecimal each = total.divide(BigDecimal.valueOf(n), PENCE, RoundingMode.DOWN);
        BigDecimal remainder = total.subtract(each.multiply(BigDecimal.valueOf(n)));
        List<BigDecimal> out = new ArrayList<>(n);
        out.add(each.add(remainder));
        for (int i = 1; i < n; i++) {
            out.add(each);
        }
        return out;
    }
}
