# gridline-telemetry

Feeder-head telemetry processing for the distribution control room (DMS).
RTUs report active power per feeder every 1–5 s via the SCADA front-end and
the historian; this library parses, quality-filters and aggregates those
readings for the loading report and the load-forecasting feed.

## Modules

| Package | Purpose |
| --- | --- |
| `com.gridline.telemetry.model` | `Reading` (feeder, event time, kW, quality), `Quality` |
| `com.gridline.telemetry.ingest` | Historian CSV parser, SCADA frame parser (checksummed) |
| `com.gridline.telemetry.units` | Unit normalisation to kW |
| `com.gridline.telemetry.quality` | `QualityFilter` (drops BAD / out-of-envelope values) |
| `com.gridline.telemetry.window` | Aggregation: `WindowAggregator`, `WindowResult`, sinks, `CumulativeAggregator` |
| `com.gridline.telemetry.report` | Control-room feeder loading report |
| `com.gridline.telemetry.pipeline` | `TelemetryPipeline` glue + `PipelineMetrics` |

## Conventions

* Java 17, standard library only (the library is embedded in the DMS adapter,
  which forbids third-party jars). No Maven/Gradle in the build sandbox: tests
  use the tiny in-repo `testkit` (`@testkit.Test`, `testkit.Assert`).
* Run tests: `scripts/test.sh` (optionally a class-name regex).
* Time is always **event time** in epoch milliseconds UTC (`Reading.timestampMillis`),
  never wall-clock time. Windows are half-open `[start, end)`.
* Power is `double` kW; negative means reverse flow (PV export).
* Aggregators are single-threaded (one consumer thread); anything shared
  between ingest threads and the consumer must be thread-safe.
* Existing public APIs are used by the DMS adapter: extend, don't break.
