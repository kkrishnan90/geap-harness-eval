package com.meridianre.policy.service;

import com.meridianre.policy.model.Coverage;
import com.meridianre.policy.model.Policy;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.regex.Pattern;

/** Business validation of imported policies. Returns human-readable problems (empty = OK). */
public final class PolicyValidator {
    private static final Pattern NUMBER = Pattern.compile("^[A-Z]{2}-\\d{4}-\\d{6}$");
    private static final Set<String> CURRENCIES = Set.of("EUR", "USD", "GBP", "CHF");

    public List<String> validate(Policy p) {
        List<String> problems = new ArrayList<>();
        if (p.policyNumber() == null || !NUMBER.matcher(p.policyNumber()).matches()) {
            problems.add("bad policy number");
        }
        if (p.holder() == null) problems.add("missing holder");
        if (p.inception() == null || p.expiry() == null || !p.expiry().isAfter(p.inception())) {
            problems.add("expiry must be after inception");
        }
        if (!CURRENCIES.contains(p.currency())) problems.add("unsupported currency " + p.currency());
        if (p.coverages().isEmpty()) problems.add("no coverages");
        for (Coverage c : p.coverages()) {
            if (c.limit().signum() <= 0) problems.add(c.code() + ": limit must be positive");
            if (c.deductible().signum() < 0 || c.deductible().compareTo(c.limit()) >= 0) {
                problems.add(c.code() + ": deductible out of range");
            }
            if (c.rate().signum() <= 0 || c.rate().compareTo(BigDecimal.ONE) > 0) {
                problems.add(c.code() + ": rate out of range");
            }
        }
        return problems;
    }
}
