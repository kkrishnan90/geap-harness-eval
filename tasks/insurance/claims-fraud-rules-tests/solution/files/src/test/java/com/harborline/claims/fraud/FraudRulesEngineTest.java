package com.harborline.claims.fraud;

import static testkit.Assert.*;

import com.harborline.claims.model.Claim;
import com.harborline.claims.model.ClaimHistory;
import com.harborline.claims.model.PriorClaim;
import java.time.LocalDate;
import java.util.List;
import testkit.Test;

/** Rule-by-rule boundary tests for the SIU rule book (docs/fraud-rules.md). */
public class FraudRulesEngineTest {
    private static final LocalDate INCEPTION = LocalDate.of(2025, 1, 1);
    private static final LocalDate LOSS = LocalDate.of(2026, 3, 15);
    private static final String IBAN = "GB82WEST12345698765432";

    private final FraudRulesEngine engine = new FraudRulesEngine();

    private static Claim.Builder base() {
        return Claim.builder().claimId("CL-2026-000500").policyId("P-77").claimantId("C-1")
                .policyInception(INCEPTION).lossDate(LOSS).reportedDate(LOSS.plusDays(2))
                .amount("2500.50").payoutIban(IBAN);
    }

    private FraudAssessment eval(Claim c) { return engine.evaluate(c, ClaimHistory.empty()); }

    private FraudAssessment eval(Claim c, PriorClaim... prior) { return engine.evaluate(c, new ClaimHistory(List.of(prior))); }

    // EARLY_CLAIM
    @Test
    public void earlyClaimFiresOnDayThirty() {
        FraudAssessment a = eval(base().policyInception(LOSS.minusDays(30)).build());
        assertEquals(List.of(RuleCode.EARLY_CLAIM), a.triggered());
        assertEquals(25, a.score());
    }

    @Test
    public void earlyClaimFiresOnInceptionDay() {
        assertTrue(eval(base().policyInception(LOSS).build()).has(RuleCode.EARLY_CLAIM));
    }

    @Test
    public void earlyClaimDoesNotFireOnDayThirtyOne() {
        assertFalse(eval(base().policyInception(LOSS.minusDays(31)).build()).has(RuleCode.EARLY_CLAIM));
    }

    @Test
    public void lossBeforeInceptionIsNotEarlyClaim() {
        assertFalse(eval(base().policyInception(LOSS.plusDays(1)).build()).has(RuleCode.EARLY_CLAIM));
    }

    // HIGH_AMOUNT
    @Test
    public void highAmountAtExactlyTenThousand() {
        FraudAssessment a = eval(base().amount("10000.00").build());
        assertTrue(a.has(RuleCode.HIGH_AMOUNT), a.toString());
    }

    @Test
    public void highAmountJustBelow() {
        assertFalse(eval(base().amount("9999.99").build()).has(RuleCode.HIGH_AMOUNT));
    }

    // FREQUENT_CLAIMANT
    private static PriorClaim prior(String id, String claimant, LocalDate loss) {
        return new PriorClaim(id, claimant, loss, "DE89370400440532013000");
    }

    @Test
    public void threePriorClaimsInWindowFire() {
        FraudAssessment a = eval(base().build(),
                prior("A", "C-1", LOSS.minusDays(365)), prior("B", "C-1", LOSS.minusDays(100)), prior("C", "C-1", LOSS.minusDays(1)));
        assertEquals(List.of(RuleCode.FREQUENT_CLAIMANT), a.triggered());
        assertEquals(30, a.score());
        assertEquals(Decision.MANUAL_REVIEW, a.decision());
    }

    @Test
    public void claimOutsideWindowDoesNotCount() {
        FraudAssessment a = eval(base().build(),
                prior("A", "C-1", LOSS.minusDays(366)), prior("B", "C-1", LOSS.minusDays(100)), prior("C", "C-1", LOSS.minusDays(1)));
        assertFalse(a.has(RuleCode.FREQUENT_CLAIMANT));
    }

    @Test
    public void otherClaimantsDoNotCount() {
        FraudAssessment a = eval(base().build(),
                prior("A", "C-9", LOSS.minusDays(10)), prior("B", "C-1", LOSS.minusDays(100)), prior("C", "C-1", LOSS.minusDays(1)));
        assertFalse(a.has(RuleCode.FREQUENT_CLAIMANT));
    }

    @Test
    public void sameDayAndSelfDoNotCount() {
        FraudAssessment a = eval(base().build(),
                prior("CL-2026-000500", "C-1", LOSS.minusDays(5)), prior("B", "C-1", LOSS), prior("C", "C-1", LOSS.minusDays(1)),
                prior("D", "C-1", LOSS.minusDays(2)));
        assertFalse(a.has(RuleCode.FREQUENT_CLAIMANT));
    }

    // LATE_REPORTING
    @Test
    public void reportedOnDaySixtyIsOnTime() {
        assertFalse(eval(base().reportedDate(LOSS.plusDays(60)).build()).has(RuleCode.LATE_REPORTING));
    }

    @Test
    public void reportedOnDaySixtyOneIsLate() {
        FraudAssessment a = eval(base().reportedDate(LOSS.plusDays(61)).build());
        assertEquals(List.of(RuleCode.LATE_REPORTING), a.triggered());
        assertEquals(15, a.score());
    }

    // SHARED_BANK_ACCOUNT
    @Test
    public void ibanOfOtherClaimantFires() {
        FraudAssessment a = eval(base().build(), new PriorClaim("X", "C-2", LOSS.minusYears(3), IBAN));
        assertTrue(a.has(RuleCode.SHARED_BANK_ACCOUNT));
        assertEquals(40, a.score());
        assertEquals(Decision.MANUAL_REVIEW, a.decision());
    }

    @Test
    public void ibanComparisonIgnoresSpacesAndCase() {
        FraudAssessment a = eval(base().build(), new PriorClaim("X", "C-2", LOSS.minusYears(3), "gb82 west 1234 5698 7654 32"));
        assertTrue(a.has(RuleCode.SHARED_BANK_ACCOUNT), a.toString());
    }

    @Test
    public void ownIbanReuseDoesNotFire() {
        assertFalse(eval(base().build(), new PriorClaim("X", "C-1", LOSS.minusYears(3), IBAN)).has(RuleCode.SHARED_BANK_ACCOUNT));
    }

    // ROUND_AMOUNT
    @Test
    public void roundAmountsByValue() {
        assertTrue(eval(base().amount("3000").build()).has(RuleCode.ROUND_AMOUNT));
        assertTrue(eval(base().amount("3000.00").build()).has(RuleCode.ROUND_AMOUNT));
        assertFalse(eval(base().amount("3000.01").build()).has(RuleCode.ROUND_AMOUNT));
        assertFalse(eval(base().amount("999.99").build()).has(RuleCode.ROUND_AMOUNT));
    }

    // Decision bands
    @Test
    public void scoreSixtyIsReferredToSiu() {
        // EARLY_CLAIM 25 + FREQUENT 30 + ROUND 5 = 60
        FraudAssessment a = eval(base().policyInception(LOSS.minusDays(3)).amount("2000.00").build(),
                prior("A", "C-1", LOSS.minusDays(20)), prior("B", "C-1", LOSS.minusDays(40)), prior("C", "C-1", LOSS.minusDays(60)));
        assertEquals(60, a.score());
        assertEquals(List.of(RuleCode.EARLY_CLAIM, RuleCode.FREQUENT_CLAIMANT, RuleCode.ROUND_AMOUNT), a.triggered());
        assertEquals(Decision.REFER_TO_SIU, a.decision());
    }

    @Test
    public void scoreBelowThirtyIsAutoApproved() {
        FraudAssessment a = eval(base().policyInception(LOSS.minusDays(3)).build());
        assertEquals(25, a.score());
        assertEquals(Decision.AUTO_APPROVE, a.decision());
    }

    @Test
    public void smallClaimFastTracked() {
        FraudAssessment a = eval(base().amount("499.99").policyInception(LOSS.minusDays(1)).reportedDate(LOSS.plusDays(90)).build());
        assertEquals(40, a.score());
        assertEquals(Decision.AUTO_APPROVE, a.decision());
    }

    @Test
    public void smallClaimWithSharedAccountNotFastTracked() {
        FraudAssessment a = eval(base().amount("120.00").policyInception(LOSS.minusDays(1)).build(),
                new PriorClaim("X", "C-2", LOSS.minusYears(1), IBAN));
        assertEquals(65, a.score());
        assertEquals(Decision.REFER_TO_SIU, a.decision());
    }

    @Test
    public void fiveHundredIsNotFastTracked() {
        FraudAssessment a = eval(base().amount("500.00").policyInception(LOSS.minusDays(1)).reportedDate(LOSS.plusDays(90)).build());
        assertEquals(Decision.MANUAL_REVIEW, a.decision());
    }
}
