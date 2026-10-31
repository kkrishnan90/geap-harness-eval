package com.brightmart.loyalty.points;

import com.brightmart.loyalty.model.Category;
import java.math.BigDecimal;
import java.math.RoundingMode;

/** 1 point per whole pound spent, times the category multiplier. Pharmacy and gift cards never earn. */
public final class EarnRules {
    private EarnRules() {}

    public static int pointsFor(BigDecimal spend, Category category) {
        if (spend.signum() <= 0) return 0;
        return spend.setScale(0, RoundingMode.FLOOR).intValueExact() * category.multiplier();
    }
}
