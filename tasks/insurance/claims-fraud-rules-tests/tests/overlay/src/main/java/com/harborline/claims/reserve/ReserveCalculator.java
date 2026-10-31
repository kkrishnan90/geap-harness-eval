package com.harborline.claims.reserve;

import java.math.BigDecimal;
import java.math.RoundingMode;

/** Initial case reserve = claimed amount x line-of-business loading, rounded up to whole pounds. */
public final class ReserveCalculator {
    public enum Line { MOTOR, HOME, TRAVEL }

    public BigDecimal initialReserve(Line line, BigDecimal claimed) {
        BigDecimal loading;
        switch (line) {
            case MOTOR: loading = new BigDecimal("1.15"); break;
            case HOME: loading = new BigDecimal("1.25"); break;
            default: loading = new BigDecimal("1.05"); break;
        }
        return claimed.multiply(loading).setScale(0, RoundingMode.CEILING).setScale(2);
    }
}
