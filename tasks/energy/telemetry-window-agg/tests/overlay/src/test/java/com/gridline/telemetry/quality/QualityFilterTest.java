package com.gridline.telemetry.quality;

import static testkit.Assert.*;

import com.gridline.telemetry.model.Quality;
import com.gridline.telemetry.model.Reading;
import testkit.Test;

public class QualityFilterTest {
    @Test
    public void dropsBadAndOutOfRange() {
        QualityFilter f = new QualityFilter(5000);
        assertTrue(f.accept(Reading.good("F1", 0, 4999)));
        assertTrue(f.accept(Reading.good("F1", 0, -5000)));
        assertFalse(f.accept(Reading.good("F1", 0, 5000.5)));
        assertFalse(f.accept(new Reading("F1", 0, 10, Quality.BAD)));
        assertTrue(f.accept(new Reading("F1", 0, 10, Quality.SUSPECT)));
        assertEquals(1L, f.droppedCount(QualityFilter.Reason.OUT_OF_RANGE));
        assertEquals(1L, f.droppedCount(QualityFilter.Reason.BAD_QUALITY));
        assertEquals(1L, f.suspectPassed());
    }

    @Test
    public void readingValidation() {
        assertThrows(IllegalArgumentException.class, () -> Reading.good(" ", 0, 1));
        assertThrows(IllegalArgumentException.class, () -> Reading.good("F1", 0, Double.NaN));
        assertThrows(IllegalArgumentException.class, () -> Quality.fromCode("X"));
    }
}
