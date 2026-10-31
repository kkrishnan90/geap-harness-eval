# TCU-3318: IMU samples lost/corrupted after ~5 days uptime (SPSC ring)

**Component:** sensorhub-fw / `src/spsc_ring.c` · **Priority:** Critical · **Type:** Bug

## Context

Field units of the telematics control unit report a burst of crash-detection
false positives after roughly 4.9 days of uptime at the 10 kHz IMU rate.
The IMU ISR pushes `sensor_sample_t` into the lock-free single-producer /
single-consumer ring (`include/spsc_ring.h`), and the fusion task drains it with
`spsc_pop()` / `spsc_pop_batch()`. 2^32 samples at 10 kHz is ~4.97 days — the
moment the free-running `head` counter wraps.

The design contract is documented in `README.md` ("Ring buffer design"). The
implementation does not follow it:

- The fill level is wrong as soon as `head` has wrapped around 2^32 while
  `tail` has not (the producer believes the ring is full and drops samples,
  the consumer believes there are more samples than were written and reads
  stale slots).
- `spsc_full()` reports *full* one sample early (legacy "one empty slot"
  convention), while `spsc_push()` accepts all `capacity` samples.
- `spsc_pop_batch()` returns wrong samples when the readable region wraps
  past the physical end of the slot array.
- On the dual-core bench build (and on the arm64 host) the threaded soak test
  occasionally sees torn samples: the producer/consumer counter publication
  uses relaxed atomics where the contract requires release/acquire.

## Expected behaviour

- All `capacity` slots are usable. With free-running counters, the fill level
  is `head - tail` (mod 2^32) at every point, including when either counter
  wraps; `spsc_size`, `spsc_free`, `spsc_empty`, `spsc_full`, `spsc_push`,
  `spsc_pop` and `spsc_pop_batch` all agree with it. `spsc_full()` is true
  exactly when `capacity` samples are stored.
- `spsc_pop_batch(r, out, max)` returns `min(max, size)` samples in FIFO order,
  correctly handling a region that wraps past the end of the slot array and
  a counter wrap at 2^32.
- Memory ordering per README: the producer writes the slot then
  release-stores `head`, and acquire-loads `tail`; the consumer acquire-loads
  `head`, copies the slot(s), then release-stores `tail`.
- A producer thread and consumer thread streaming hundreds of thousands of
  samples through a small ring, starting just below the 2^32 wrap (set with
  `spsc_debug_set_counters()`), must deliver every sample exactly once, in
  order and untorn, with both `spsc_pop` and `spsc_pop_batch`.

## Constraints

- Do not change `include/spsc_ring.h` (struct layout and signatures are
  shared with the ISR code); no locks, no OS calls in `src/`.
- C11 only. Existing tests keep passing: `make test`.
