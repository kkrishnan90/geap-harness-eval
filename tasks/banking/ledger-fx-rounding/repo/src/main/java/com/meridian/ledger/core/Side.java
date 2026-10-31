package com.meridian.ledger.core;

public enum Side {
    DEBIT, CREDIT;

    public Side opposite() { return this == DEBIT ? CREDIT : DEBIT; }

    /** +1 for debit, -1 for credit (balances are kept debit-positive). */
    public int sign() { return this == DEBIT ? 1 : -1; }
}
