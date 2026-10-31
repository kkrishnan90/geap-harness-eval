package com.harborline.claims.fraud;

import static testkit.Assert.*;

import com.harborline.claims.model.Claim;
import com.harborline.claims.model.ClaimHistory;
import java.time.LocalDate;
import testkit.Test;

public class FraudRulesEngineSmokeTest {
    @Test
    public void cleanClaimIsAutoApproved() {
        Claim c = Claim.builder().claimId("CL-2026-000101").policyId("P-1").claimantId("C-1")
                .policyInception(LocalDate.of(2025, 1, 1)).lossDate(LocalDate.of(2026, 2, 10))
                .reportedDate(LocalDate.of(2026, 2, 11)).amount("1250.40")
                .payoutIban("GB82WEST12345698765432").build();
        FraudAssessment a = new FraudRulesEngine().evaluate(c, ClaimHistory.empty());
        assertEquals(0, a.score());
        assertEquals(Decision.AUTO_APPROVE, a.decision());
    }

    @Test
    public void claimBuilderValidatesDates() {
        assertThrows(IllegalArgumentException.class, () -> Claim.builder().claimId("x").policyId("p").claimantId("c")
                .policyInception(LocalDate.of(2025, 1, 1)).lossDate(LocalDate.of(2026, 2, 10))
                .reportedDate(LocalDate.of(2026, 2, 9)).amount("10").payoutIban("GB").build());
    }
}
