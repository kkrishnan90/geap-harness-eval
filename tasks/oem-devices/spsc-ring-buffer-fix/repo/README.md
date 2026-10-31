# sensorhub-fw (IMU acquisition path)

Part of the sensor-hub MCU firmware for the telematics control unit (TCU). The
IMU driver runs in the SPI DMA-complete ISR (producer) and pushes samples into
a lock-free single-producer / single-consumer ring; the fusion task (consumer)
drains it in batches, filters the samples and packs them into frames for the
application processor.

## Modules

| File | Purpose |
| --- | --- |
| `include/spsc_ring.h`, `src/spsc_ring.c` | Lock-free SPSC ring of `sensor_sample_t` (C11 `<stdatomic.h>`) |
| `include/sample.h` | Sample layout shared with the driver |
| `include/lowpass.h`, `src/lowpass.c` | Q15 fixed-point first-order low-pass filter |
| `include/imu_frame.h`, `src/imu_frame.c` | Packing samples into the 64-byte IPC frame (+ CRC-16/CCITT) |

## Ring buffer design

* Capacity is a power of two between 2 and 2^31. **All `capacity` slots are
  usable** (we do not sacrifice a slot to tell full from empty).
* `head` and `tail` are free-running `uint32_t` counters (total pushed / total
  popped). They are never masked when stored; the slot index is
  `counter & (capacity - 1)`. The fill level is `head - tail` in modulo-2^32
  arithmetic, which stays correct when the counters wrap around 2^32
  (after ~5 days at 10 kHz).
* Only the producer writes `head`, only the consumer writes `tail`.
  Publication uses release/acquire: the producer writes the slot, then
  release-stores `head`; the consumer acquire-loads `head` before reading a
  slot, and release-stores `tail` after it has finished copying the slot(s);
  the producer acquire-loads `tail` before reusing a slot.
* `spsc_debug_set_counters()` exists for HIL tests that need to start near the
  wrap point; it must only be called while no producer/consumer is running.

## Conventions

* C11, no dynamic allocation, no OS calls in `src/` (the code also builds for
  the Cortex-M4 target with arm-none-eabi-gcc).
* Public headers are frozen: do not change signatures or struct layout.
* Build and test on the host: `make test` (clang, `-std=c11 -Wall -Wextra -Werror`).
