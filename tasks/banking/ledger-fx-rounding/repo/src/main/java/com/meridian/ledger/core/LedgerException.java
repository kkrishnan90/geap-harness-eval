package com.meridian.ledger.core;

/** A journal entry was refused; the ledger is unchanged. */
public class LedgerException extends RuntimeException {
    public LedgerException(String message) { super(message); }
}
