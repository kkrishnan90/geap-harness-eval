#ifndef SPSC_RING_H
#define SPSC_RING_H

/* Lock-free single-producer / single-consumer ring of sensor samples.
 * See README.md "Ring buffer design" for the counter and memory-ordering contract. */

#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>

#include "sample.h"

typedef struct {
    _Atomic uint32_t head;   /* total samples pushed (producer-owned) */
    _Atomic uint32_t tail;   /* total samples popped (consumer-owned) */
    uint32_t capacity;       /* power of two */
    uint32_t mask;           /* capacity - 1 */
    sensor_sample_t *slots;  /* caller-provided storage of `capacity` samples */
} spsc_ring_t;

/* Returns 0, or -1 if r/storage is NULL or capacity is not a power of two in [2, 2^31]. */
int spsc_init(spsc_ring_t *r, sensor_sample_t *storage, uint32_t capacity);

/* Producer side. Returns false (and changes nothing) if the ring is full. */
bool spsc_push(spsc_ring_t *r, const sensor_sample_t *s);

/* Consumer side. Returns false (out untouched) if the ring is empty. */
bool spsc_pop(spsc_ring_t *r, sensor_sample_t *out);

/* Consumer side. Pops up to max samples in FIFO order into out[]; returns the number popped. */
uint32_t spsc_pop_batch(spsc_ring_t *r, sensor_sample_t *out, uint32_t max);

/* Number of samples currently stored / free slots. Exact when called from either side
 * while the other side is idle; otherwise a snapshot. */
uint32_t spsc_size(const spsc_ring_t *r);
uint32_t spsc_free(const spsc_ring_t *r);
bool spsc_empty(const spsc_ring_t *r);
bool spsc_full(const spsc_ring_t *r);

/* HIL/test hook: set both counters (only while producer and consumer are stopped). */
void spsc_debug_set_counters(spsc_ring_t *r, uint32_t head, uint32_t tail);

#endif
