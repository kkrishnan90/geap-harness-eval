package com.gridline.telemetry.window;

/** Receives closed windows (e.g. the Kafka producer to the load-forecasting topic). */
@FunctionalInterface
public interface WindowSink {
    void emit(WindowResult result);
}
