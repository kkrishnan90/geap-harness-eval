package com.harborline.motor.policy;

/**
 * Policy numbers: "HM" + 8 digit sequence + Luhn check digit, e.g. HM000012343.
 */
public final class PolicyNumberGenerator {
    private long next;

    public PolicyNumberGenerator(long start) { this.next = start; }

    public synchronized String next() {
        String seq = String.format("%08d", next++);
        return "HM" + seq + luhn(seq);
    }

    static int luhn(String digits) {
        int sum = 0;
        boolean dbl = true;
        for (int i = digits.length() - 1; i >= 0; i--) {
            int d = digits.charAt(i) - '0';
            if (dbl) { d *= 2; if (d > 9) d -= 9; }
            sum += d;
            dbl = !dbl;
        }
        return (10 - sum % 10) % 10;
    }

    public static boolean isValid(String policyNumber) {
        if (policyNumber == null || !policyNumber.matches("HM\\d{9}")) return false;
        String seq = policyNumber.substring(2, 10);
        return luhn(seq) == policyNumber.charAt(10) - '0';
    }
}
