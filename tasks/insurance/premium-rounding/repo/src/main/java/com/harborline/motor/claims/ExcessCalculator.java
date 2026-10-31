package com.harborline.motor.claims;

import java.math.BigDecimal;

/** Compulsory + voluntary excess applied at first notification of loss. */
public final class ExcessCalculator {
    public static final BigDecimal YOUNG_DRIVER_EXCESS = new BigDecimal("250.00");
    public static final BigDecimal WINDSCREEN_EXCESS = new BigDecimal("75.00");

    public BigDecimal totalExcess(BigDecimal compulsory, BigDecimal voluntary, int driverAge, boolean windscreenOnly) {
        if (windscreenOnly) return WINDSCREEN_EXCESS;
        BigDecimal total = compulsory.add(voluntary);
        if (driverAge < 25) total = total.add(YOUNG_DRIVER_EXCESS);
        return total.setScale(2);
    }

    /** Amount paid to the policyholder; never negative. */
    public BigDecimal settlement(BigDecimal assessedLoss, BigDecimal excess) {
        BigDecimal s = assessedLoss.subtract(excess);
        return s.signum() < 0 ? BigDecimal.ZERO.setScale(2) : s.setScale(2);
    }
}
