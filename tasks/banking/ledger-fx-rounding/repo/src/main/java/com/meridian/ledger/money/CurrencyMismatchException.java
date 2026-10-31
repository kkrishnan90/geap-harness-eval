package com.meridian.ledger.money;

public class CurrencyMismatchException extends IllegalArgumentException {
    public CurrencyMismatchException(String message) { super(message); }
}
