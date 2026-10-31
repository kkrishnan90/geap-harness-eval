package com.northbank.payments.calendar;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.LocalTime;
import java.util.HashSet;
import java.util.Set;

/**
 * TARGET2 closing days and the gateway's cut-off for same-day execution.
 * Used by the scheduler to roll requested execution dates; unrelated to parsing.
 */
public final class TargetCalendar {
    public static final LocalTime SAME_DAY_CUTOFF = LocalTime.of(15, 30);

    private final Set<LocalDate> extraClosingDays = new HashSet<>();

    public void addClosingDay(LocalDate d) { extraClosingDays.add(d); }

    public boolean isBusinessDay(LocalDate d) {
        DayOfWeek w = d.getDayOfWeek();
        if (w == DayOfWeek.SATURDAY || w == DayOfWeek.SUNDAY) return false;
        if (extraClosingDays.contains(d)) return false;
        int m = d.getMonthValue(), day = d.getDayOfMonth();
        if (m == 1 && day == 1) return false;           // New Year's Day
        if (m == 5 && day == 1) return false;           // Labour Day
        if (m == 12 && (day == 25 || day == 26)) return false;
        LocalDate easter = easterSunday(d.getYear());
        return !d.equals(easter.minusDays(2)) && !d.equals(easter.plusDays(1));
    }

    public LocalDate nextBusinessDay(LocalDate d) {
        LocalDate x = d.plusDays(1);
        while (!isBusinessDay(x)) x = x.plusDays(1);
        return x;
    }

    /** First business day on which a payment received at (date, time) can be executed. */
    public LocalDate earliestExecution(LocalDate date, LocalTime receivedAt) {
        if (isBusinessDay(date) && !receivedAt.isAfter(SAME_DAY_CUTOFF)) return date;
        return nextBusinessDay(date);
    }

    /** Anonymous Gregorian algorithm (Meeus/Jones/Butcher). */
    static LocalDate easterSunday(int y) {
        int a = y % 19, b = y / 100, c = y % 100, d = b / 4, e = b % 4;
        int f = (b + 8) / 25, g = (b - f + 1) / 3, h = (19 * a + b - d - g + 15) % 30;
        int i = c / 4, k = c % 4, l = (32 + 2 * e + 2 * i - h - k) % 7;
        int m = (a + 11 * h + 22 * l) / 451;
        int month = (h + l - 7 * m + 114) / 31, day = ((h + l - 7 * m + 114) % 31) + 1;
        return LocalDate.of(y, month, day);
    }
}
