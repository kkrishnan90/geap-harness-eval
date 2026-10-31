package com.northbank.payments.calendar;

import testkit.Test;

import java.time.LocalDate;
import java.time.LocalTime;

import static testkit.Assert.*;

public class TargetCalendarTest {
    @Test
    public void easterHolidays2025() {
        TargetCalendar c = new TargetCalendar();
        assertFalse(c.isBusinessDay(LocalDate.of(2025, 4, 18)), "Good Friday");
        assertFalse(c.isBusinessDay(LocalDate.of(2025, 4, 21)), "Easter Monday");
        assertTrue(c.isBusinessDay(LocalDate.of(2025, 4, 22)));
    }

    @Test
    public void cutoffRollsToNextBusinessDay() {
        TargetCalendar c = new TargetCalendar();
        LocalDate fri = LocalDate.of(2025, 3, 14);
        assertEquals(fri, c.earliestExecution(fri, LocalTime.of(15, 30)));
        assertEquals(LocalDate.of(2025, 3, 17), c.earliestExecution(fri, LocalTime.of(15, 31)));
    }

    @Test
    public void christmasWeek() {
        TargetCalendar c = new TargetCalendar();
        assertEquals(LocalDate.of(2025, 12, 29), c.nextBusinessDay(LocalDate.of(2025, 12, 24)));
    }
}
