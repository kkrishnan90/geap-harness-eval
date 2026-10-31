package com.gridline.telemetry.model;

import java.util.Objects;

/**
 * One active-power sample from a feeder-head meter.
 *
 * @param feederId        feeder identifier, e.g. {@code "SUB12-F04"}
 * @param timestampMillis event time (measurement time at the RTU), epoch milliseconds UTC
 * @param valueKw         active power in kW (negative = reverse flow, e.g. PV export)
 * @param quality         quality flag from the RTU
 */
public record Reading(String feederId, long timestampMillis, double valueKw, Quality quality) {
    public Reading {
        Objects.requireNonNull(feederId, "feederId");
        Objects.requireNonNull(quality, "quality");
        if (feederId.isBlank()) throw new IllegalArgumentException("feederId blank");
        if (Double.isNaN(valueKw) || Double.isInfinite(valueKw)) throw new IllegalArgumentException("valueKw not finite");
    }

    public static Reading good(String feederId, long timestampMillis, double valueKw) {
        return new Reading(feederId, timestampMillis, valueKw, Quality.GOOD);
    }
}
