package com.northbank.payments.pain.parser;

/** Raised when a pain.001 file cannot be turned into the model. */
public class ParseException extends Exception {
    public ParseException(String message) { super(message); }
    public ParseException(String message, Throwable cause) { super(message, cause); }
}
