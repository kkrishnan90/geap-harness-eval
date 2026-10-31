package com.gridline.telemetry.window;

import com.gridline.telemetry.model.Reading;

/** Consumes readings in arrival order and emits aggregates to a {@link WindowSink}. */
public interface WindowAggregator {
    void accept(Reading reading);

    /** End of stream: emit everything still held. */
    void flush();
}
