package com.gridline.telemetry.window;

import com.gridline.telemetry.model.Reading;

/** Side output for readings that arrived after all their windows were closed. */
@FunctionalInterface
public interface LateEventSink {
    void onLate(Reading reading);
}
