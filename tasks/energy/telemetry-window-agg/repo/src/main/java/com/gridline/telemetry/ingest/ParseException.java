package com.gridline.telemetry.ingest;

/** A telemetry record could not be parsed. Carries the offending input for the dead-letter log. */
public class ParseException extends Exception {
    private final String input;

    public ParseException(String message, String input) {
        super(message + ": " + input);
        this.input = input;
    }

    public String getInput() { return input; }
}
