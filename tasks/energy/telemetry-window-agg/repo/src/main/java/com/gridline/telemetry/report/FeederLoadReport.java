package com.gridline.telemetry.report;

import com.gridline.telemetry.window.WindowResult;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Optional;

/** Renders window results for the control-room loading report and flags overloads. */
public class FeederLoadReport {
    private final double ratingKw;

    public FeederLoadReport(double ratingKw) {
        this.ratingKw = ratingKw;
    }

    public static final String HEADER = "feeder_id,window_start,window_end,samples,avg_kw,max_kw,loading_pct";

    public List<String> render(List<WindowResult> results) {
        List<String> out = new ArrayList<>();
        out.add(HEADER);
        for (WindowResult r : results) {
            out.add(String.format(Locale.ROOT, "%s,%s,%s,%d,%.3f,%.3f,%.1f",
                r.feederId(), Instant.ofEpochMilli(r.windowStart()), Instant.ofEpochMilli(r.windowEnd()),
                r.count(), r.avgKw(), r.maxKw(), loadingPct(r)));
        }
        return out;
    }

    /** Average loading as a percentage of the feeder rating. */
    public double loadingPct(WindowResult r) {
        return 100.0 * Math.abs(r.avgKw()) / ratingKw;
    }

    public List<WindowResult> overloads(List<WindowResult> results, double thresholdPct) {
        List<WindowResult> out = new ArrayList<>();
        for (WindowResult r : results) if (loadingPct(r) > thresholdPct) out.add(r);
        return out;
    }

    public Optional<WindowResult> peak(List<WindowResult> results) {
        return results.stream().max(Comparator.comparingDouble(WindowResult::avgKw));
    }
}
