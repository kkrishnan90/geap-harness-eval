package com.meridianre.policy.rating;

import com.meridianre.policy.model.Coverage;
import com.meridianre.policy.model.Policy;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.temporal.ChronoUnit;

/** Technical premium: sum(rate * (limit - deductible)), pro-rated by days in force over 365. */
public final class PremiumCalculator {
    public BigDecimal annualPremium(Policy p) {
        BigDecimal total = BigDecimal.ZERO;
        for (Coverage c : p.coverages()) {
            total = total.add(c.rate().multiply(c.limit().subtract(c.deductible())));
        }
        return total.setScale(2, RoundingMode.HALF_EVEN);
    }

    public BigDecimal termPremium(Policy p) {
        long days = ChronoUnit.DAYS.between(p.inception(), p.expiry());
        return annualPremium(p).multiply(BigDecimal.valueOf(days))
                .divide(BigDecimal.valueOf(365), 2, RoundingMode.HALF_EVEN);
    }
}
