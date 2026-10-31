package com.brightmart.loyalty.model;

/** Basket categories with their earn multipliers. */
public enum Category {
    GROCERY(1), FUEL(1), HOME(2), ELECTRONICS(2), PHARMACY(0), GIFT_CARDS(0);

    private final int multiplier;

    Category(int multiplier) { this.multiplier = multiplier; }

    public int multiplier() { return multiplier; }
}
