package com.harborline.claims.fraud;

/** Fraud indicators, in evaluation/reporting order. Weights are set by the SIU. */
public enum RuleCode {
    EARLY_CLAIM(25),
    HIGH_AMOUNT(20),
    FREQUENT_CLAIMANT(30),
    LATE_REPORTING(15),
    SHARED_BANK_ACCOUNT(40),
    ROUND_AMOUNT(5);

    private final int weight;

    RuleCode(int weight) { this.weight = weight; }

    public int weight() { return weight; }
}
