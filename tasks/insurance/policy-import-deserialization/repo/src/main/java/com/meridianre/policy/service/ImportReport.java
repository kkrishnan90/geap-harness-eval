package com.meridianre.policy.service;

import java.util.List;
import java.util.Map;

/** Outcome of one upload. */
public record ImportReport(boolean accepted, String batchId, int imported, Map<String, List<String>> rejected,
                           String error) {

    public static ImportReport failed(String error) {
        return new ImportReport(false, null, 0, Map.of(), error);
    }
}
