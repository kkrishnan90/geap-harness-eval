package com.gridline.telemetry.window;

import java.util.ArrayList;
import java.util.List;

/** Sink that keeps results in memory, in emission order. */
public class CollectingSink implements WindowSink {
    private final List<WindowResult> results = new ArrayList<>();

    @Override
    public synchronized void emit(WindowResult result) {
        results.add(result);
    }

    public synchronized List<WindowResult> results() {
        return new ArrayList<>(results);
    }

    public synchronized void clear() {
        results.clear();
    }
}
