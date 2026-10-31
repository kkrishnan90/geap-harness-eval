package com.meridianre.policy.rating;

import com.meridianre.policy.model.Coverage;
import com.meridianre.policy.model.LineOfBusiness;
import com.meridianre.policy.model.Party;
import com.meridianre.policy.model.Policy;
import com.meridianre.policy.model.PolicyBatch;
import com.meridianre.policy.model.PolicyStatus;
import testkit.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

import static testkit.Assert.*;

public class PremiumCalculatorTest {
    static Policy policy(String number, LineOfBusiness line, PolicyStatus status) {
        Party holder = new Party("P-" + number, "Holder of " + number, "DE");
        return new Policy(number, line, holder, LocalDate.of(2026, 1, 1), LocalDate.of(2027, 1, 1), "EUR", status,
                List.of(new Coverage("FIRE", new BigDecimal("1000000.00"), new BigDecimal("5000.00"), new BigDecimal("0.0012")),
                        new Coverage("FLOOD", new BigDecimal("250000.00"), new BigDecimal("10000.00"), new BigDecimal("0.0040"))));
    }

    static PolicyBatch batch(int n) {
        List<Policy> list = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            list.add(policy(String.format("PR-2026-%06d", i + 1), LineOfBusiness.PROPERTY, PolicyStatus.BOUND));
        }
        return new PolicyBatch("B-20260301-01", "PAS-LEGACY", list);
    }

    @Test
    public void annualPremium() {
        // 0.0012 * 995000 + 0.0040 * 240000 = 1194 + 960
        assertAmount("2154.00", new PremiumCalculator().annualPremium(policy("PR-2026-000001", LineOfBusiness.PROPERTY, PolicyStatus.BOUND)), "annual");
    }

    @Test
    public void shortTermProRata() {
        Policy p = policy("PR-2026-000002", LineOfBusiness.PROPERTY, PolicyStatus.BOUND);
        Policy half = new Policy(p.policyNumber(), p.line(), p.holder(), LocalDate.of(2026, 1, 1), LocalDate.of(2026, 7, 2),
                p.currency(), p.status(), p.coverages());
        // 182 days
        assertAmount("1074.05", new PremiumCalculator().termPremium(half), "term");
    }
}
