package com.harborline.claims.intake;

import java.time.LocalDate;

/** Claim numbers: CL-YYYY-NNNNNN, sequence per year. */
public final class ClaimNumberFormat {
    private ClaimNumberFormat() {}

    public static String format(LocalDate registered, int sequence) {
        if (sequence < 1 || sequence > 999_999) throw new IllegalArgumentException("sequence out of range");
        return String.format("CL-%04d-%06d", registered.getYear(), sequence);
    }

    public static boolean isValid(String claimNumber) {
        return claimNumber != null && claimNumber.matches("CL-\\d{4}-\\d{6}") && !claimNumber.endsWith("000000");
    }
}
