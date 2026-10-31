package com.harborline.claims.fraud;

import java.util.List;

/** Outcome of fraud screening for one claim. */
public final class FraudAssessment {
    private final int score;
    private final List<RuleCode> triggered;
    private final Decision decision;

    public FraudAssessment(int score, List<RuleCode> triggered, Decision decision) {
        this.score = score;
        this.triggered = List.copyOf(triggered);
        this.decision = decision;
    }

    public int score() { return score; }
    /** Triggered indicators in {@link RuleCode} declaration order. */
    public List<RuleCode> triggered() { return triggered; }
    public Decision decision() { return decision; }

    public boolean has(RuleCode code) { return triggered.contains(code); }

    @Override
    public String toString() {
        return "FraudAssessment{score=" + score + ", triggered=" + triggered + ", decision=" + decision + "}";
    }
}
