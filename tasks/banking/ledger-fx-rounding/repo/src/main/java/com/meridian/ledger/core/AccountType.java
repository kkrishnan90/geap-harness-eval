package com.meridian.ledger.core;

public enum AccountType {
    ASSET, LIABILITY, EQUITY, INCOME, EXPENSE;

    /** Monetary balance-sheet accounts are revalued at closing rates (IAS 21). */
    public boolean isMonetary() { return this == ASSET || this == LIABILITY; }
}
