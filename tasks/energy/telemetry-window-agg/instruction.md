# DMS-1874: Windowed feeder-load aggregation (event time) + bounded ingest buffer

**Component:** gridline-telemetry · **Type:** Feature · **Priority:** High

## Context

The load-forecasting team needs per-feeder power aggregates over fixed
(tumbling) and overlapping (sliding) windows, computed on **event time**. RTU
data arrives out of order (store-and-forward after comms outages), so we need
a watermark with configurable allowed lateness, and readings that arrive
after their windows are closed must be routed to a side output instead of
silently corrupting already-published aggregates.

Separately, during last month's storm the SCADA front-end burst at 40x normal
rate and the unbounded batch path ran the adapter out of heap. Ingest must
go through a bounded buffer with an explicit overflow policy.

## Scope

Implement in the existing codebase (all new types are public):

### 1. `com.gridline.telemetry.window.WindowSpec`

- `static WindowSpec tumbling(long sizeMillis)` and
  `static WindowSpec sliding(long sizeMillis, long slideMillis)`;
  accessors `long sizeMillis()`, `long slideMillis()` (tumbling: slide == size).
- `IllegalArgumentException` if size <= 0, slide <= 0, slide > size, or size
  is not a multiple of slide.
- Windows are aligned to the epoch: they start at every multiple of
  `slideMillis` and cover `[start, start + size)`. A reading at `ts` belongs
  to every window with `start <= ts < start + size` (one window for
  tumbling, `size / slide` windows for sliding).

### 2. `com.gridline.telemetry.window.LateEventSink`

Functional interface: `void onLate(Reading reading)`.

### 3. `com.gridline.telemetry.window.EventTimeWindowAggregator implements WindowAggregator`

Constructor `EventTimeWindowAggregator(WindowSpec spec, long allowedLatenessMillis, WindowSink sink, LateEventSink lateSink)`
(`IllegalArgumentException` if lateness < 0). Aggregates **per feeder**.

On `accept(reading)`, in this order:

1. Update the watermark: `watermark = (max event time seen so far) - allowedLatenessMillis`.
   It never moves backwards. `long watermark()` returns it (`Long.MIN_VALUE`
   before the first reading).
2. Add the reading to each of its windows whose end is **greater than** the
   watermark. If it has no such window, it is *late*: pass it to
   `lateSink.onLate`, increment `long lateEventCount()`, and change nothing
   else. (A sliding-window reading that still has at least one open window is
   not late; it is added to the open windows only.)
3. Emit (via `sink.emit`) and discard every held window whose end is
   `<= watermark`.

Emitted results are `WindowResult(feederId, windowStart, windowEnd, count, sumKw, minKw, maxKw)`.
Windows with no readings are never emitted. Whenever several windows are
emitted at once, the order is by `windowEnd` ascending, then `feederId`
ascending (`String` natural order). `flush()` emits all remaining held
windows in the same order and leaves no state behind.

`int openWindowCount()` returns the number of (feeder, window) aggregates
currently held — memory must stay bounded on an endless in-order stream.

### 4. `com.gridline.telemetry.buffer.OverflowPolicy` and `BoundedReadingBuffer`

`enum OverflowPolicy { BLOCK, DROP_OLDEST, REJECT }`

`BoundedReadingBuffer(int capacity, OverflowPolicy policy)` — thread-safe FIFO
(`IllegalArgumentException` if capacity <= 0):

- `boolean offer(Reading r, long timeout, TimeUnit unit) throws InterruptedException`
  - space available: enqueue, `true`.
  - full + `BLOCK`: wait up to the timeout for space; `true` once enqueued,
    `false` if still full when the timeout elapses.
  - full + `DROP_OLDEST`: evict the oldest buffered reading, enqueue the new
    one, `true`, never blocks.
  - full + `REJECT`: `false` immediately, never blocks (timeout ignored).
- `Reading poll()` — oldest reading or `null` if empty; never blocks; frees
  space for blocked producers.
- `int size()`, `int capacity()`, `long droppedCount()` (evictions by
  `DROP_OLDEST`), `long rejectedCount()` (every `offer` that returned `false`).
- `size()` never exceeds `capacity`; no reading is lost or duplicated
  except by `DROP_OLDEST` eviction; order is FIFO.

### 5. Pipeline wiring (`com.gridline.telemetry.pipeline`)

- `PipelineMetrics`: add `void incrementRejected()` and `long rejected()`.
- `TelemetryPipeline`: add constructor
  `TelemetryPipeline(BoundedReadingBuffer buffer, QualityFilter filter, WindowAggregator aggregator, PipelineMetrics metrics)`.
  - `boolean submit(Reading r, long timeout, TimeUnit unit) throws InterruptedException`:
    increments `received`, offers to the buffer; if refused, increments
    `rejected` and returns `false`. Nothing is filtered or aggregated at
    submit time. Throws `IllegalStateException` if the pipeline was built
    without a buffer.
  - `int drain()`: on the calling thread, polls until the buffer is empty and
    sends each reading through the quality filter and aggregator exactly like
    `process` does (`filtered` / `aggregated` metrics, `received` is **not**
    incremented again). Returns the number of readings taken from the buffer
    (0 without a buffer).
  - `close()`: drains the buffer (if any), then flushes the aggregator.

## Acceptance criteria

- Behaviour exactly as specified above; existing tests (`scripts/test.sh`)
  keep passing and existing public APIs (`WindowAggregator`, `WindowResult`,
  `TelemetryPipeline(QualityFilter, WindowAggregator, PipelineMetrics)`,
  `process`, `close`, existing metrics) keep working unchanged.

## Constraints

- Java 17 standard library only. Don't modify the `testkit` package.
