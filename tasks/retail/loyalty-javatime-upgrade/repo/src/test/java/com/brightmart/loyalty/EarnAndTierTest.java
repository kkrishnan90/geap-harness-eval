package com.brightmart.loyalty;

import static testkit.Assert.*;

import com.brightmart.loyalty.catalog.RewardCatalog;
import com.brightmart.loyalty.model.Category;
import com.brightmart.loyalty.points.EarnRules;
import com.brightmart.loyalty.tier.Tier;
import com.brightmart.loyalty.tier.TierService;
import java.math.BigDecimal;
import testkit.Test;

public class EarnAndTierTest {
    @Test
    public void earnsPerWholePound() {
        assertEquals(42, EarnRules.pointsFor(new BigDecimal("42.99"), Category.GROCERY));
        assertEquals(84, EarnRules.pointsFor(new BigDecimal("42.99"), Category.HOME));
        assertEquals(0, EarnRules.pointsFor(new BigDecimal("80.00"), Category.PHARMACY));
        assertEquals(0, EarnRules.pointsFor(new BigDecimal("-5.00"), Category.GROCERY));
    }

    @Test
    public void tierThresholds() {
        TierService t = new TierService();
        assertEquals(Tier.BRONZE, t.tierFor(2_499));
        assertEquals(Tier.SILVER, t.tierFor(2_500));
        assertEquals(Tier.GOLD, t.tierFor(7_500));
        assertEquals(Tier.PLATINUM, t.tierFor(20_000));
    }

    @Test
    public void catalog() {
        RewardCatalog c = new RewardCatalog();
        assertTrue(c.canAfford("COFFEE", 150));
        assertFalse(c.canAfford("VOUCHER-10", 949));
        assertFalse(c.canAfford("UNKNOWN", 1_000_000));
    }
}
