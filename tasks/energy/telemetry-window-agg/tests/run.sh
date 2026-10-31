#!/usr/bin/env bash
# Verifier for energy/telemetry-window-agg. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
cd "$WORKDIR" || exit 0
lib_java src/test/java/testkit src/main/java src/test/java \
  com.gridline.telemetry.ingest.IngestParsersTest \
  com.gridline.telemetry.quality.QualityFilterTest \
  com.gridline.telemetry.window.CumulativeAggregatorTest \
  com.gridline.telemetry.report.FeederLoadReportTest \
  com.gridline.telemetry.pipeline.TelemetryPipelineTest \
  com.gridline.telemetry.window.WindowSpecTest \
  com.gridline.telemetry.window.TumblingWindowTest \
  com.gridline.telemetry.window.SlidingWindowTest \
  com.gridline.telemetry.window.LateEventTest \
  com.gridline.telemetry.buffer.BoundedBufferTest \
  com.gridline.telemetry.pipeline.PipelineBackpressureTest
