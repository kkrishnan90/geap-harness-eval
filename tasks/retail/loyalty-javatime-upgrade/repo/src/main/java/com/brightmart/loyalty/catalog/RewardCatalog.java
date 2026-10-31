package com.brightmart.loyalty.catalog;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

/** Rewards members can redeem points for. */
public final class RewardCatalog {
    private final Map<String, Integer> costs = new LinkedHashMap<>();

    public RewardCatalog() {
        costs.put("VOUCHER-5", 500);
        costs.put("VOUCHER-10", 950);
        costs.put("FREE-DELIVERY", 300);
        costs.put("COFFEE", 150);
    }

    public Optional<Integer> cost(String rewardCode) { return Optional.ofNullable(costs.get(rewardCode)); }

    public boolean canAfford(String rewardCode, int balance) {
        return cost(rewardCode).map(c -> balance >= c).orElse(false);
    }
}
