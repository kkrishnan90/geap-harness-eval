package com.harborline.claims.fraud;

import com.harborline.claims.model.Claim;
import com.harborline.claims.model.ClaimHistory;
import com.harborline.claims.model.PriorClaim;
import java.math.BigDecimal;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * First-line fraud screening for new claims (rule book: docs/fraud-rules.md).
 */
public final class FraudRulesEngine {

    static final BigDecimal HIGH_AMOUNT_THRESHOLD = new BigDecimal("10000.00");
    static final BigDecimal FAST_TRACK_LIMIT = new BigDecimal("500.00");
    static final BigDecimal ROUND_UNIT = new BigDecimal("1000.00");
    static final int EARLY_CLAIM_DAYS = 30;
    static final int LATE_REPORTING_DAYS = 60;
    static final int FREQUENCY_WINDOW_DAYS = 365;
    static final int FREQUENCY_MIN_PRIOR_CLAIMS = 3;
    static final int SIU_SCORE = 60;
    static final int REVIEW_SCORE = 30;

    public FraudAssessment evaluate(Claim claim, ClaimHistory history) {
        List<RuleCode> hits = new ArrayList<>();

        long daysSinceInception = ChronoUnit.DAYS.between(claim.policyInception(), claim.lossDate());
        if (daysSinceInception >= 0 && daysSinceInception <= EARLY_CLAIM_DAYS) {
            hits.add(RuleCode.EARLY_CLAIM);
        }

        if (claim.amount().compareTo(HIGH_AMOUNT_THRESHOLD) > 0) {
            hits.add(RuleCode.HIGH_AMOUNT);
        }

        int recent = 0;
        for (PriorClaim p : history.claims()) {
            if (p.claimId().equals(claim.claimId())) continue;
            if (!p.claimantId().equals(claim.claimantId())) continue;
            boolean inWindow = !p.lossDate().isBefore(claim.lossDate().minusDays(FREQUENCY_WINDOW_DAYS))
                    && p.lossDate().isBefore(claim.lossDate());
            if (inWindow) recent++;
        }
        if (recent >= FREQUENCY_MIN_PRIOR_CLAIMS) {
            hits.add(RuleCode.FREQUENT_CLAIMANT);
        }

        long reportingDelay = ChronoUnit.DAYS.between(claim.lossDate(), claim.reportedDate());
        if (reportingDelay > LATE_REPORTING_DAYS) {
            hits.add(RuleCode.LATE_REPORTING);
        }

        String iban = normaliseIban(claim.payoutIban());
        for (PriorClaim p : history.claims()) {
            if (!p.claimantId().equals(claim.claimantId()) && normaliseIban(p.payoutIban()).equals(iban)) {
                hits.add(RuleCode.SHARED_BANK_ACCOUNT);
                break;
            }
        }

        if (claim.amount().compareTo(ROUND_UNIT) >= 0
                && claim.amount().remainder(ROUND_UNIT).signum() == 0) {
            hits.add(RuleCode.ROUND_AMOUNT);
        }

        int score = 0;
        for (RuleCode c : hits) score += c.weight();
        return new FraudAssessment(score, hits, decide(claim, score, hits));
    }

    private static Decision decide(Claim claim, int score, List<RuleCode> hits) {
        if (claim.amount().compareTo(FAST_TRACK_LIMIT) < 0 && !hits.contains(RuleCode.SHARED_BANK_ACCOUNT)) {
            return Decision.AUTO_APPROVE;
        }
        if (score >= SIU_SCORE) return Decision.REFER_TO_SIU;
        if (score >= REVIEW_SCORE) return Decision.MANUAL_REVIEW;
        return Decision.AUTO_APPROVE;
    }

    static String normaliseIban(String iban) {
        return iban.replace(" ", "").toUpperCase(Locale.ROOT);
    }
}
