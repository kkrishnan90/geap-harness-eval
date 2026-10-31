#include "spsc_ring.h"

#include <stddef.h>
#include <string.h>

static uint32_t ring_count(uint32_t head, uint32_t tail, uint32_t capacity)
{
    if (head >= tail) {
        return head - tail;
    }
    /* head has wrapped around 2^32 but tail has not yet */
    return capacity - (tail - head);
}

int spsc_init(spsc_ring_t *r, sensor_sample_t *storage, uint32_t capacity)
{
    if (r == NULL || storage == NULL) {
        return -1;
    }
    if (capacity < 2u || capacity > 0x80000000u || (capacity & (capacity - 1u)) != 0u) {
        return -1;
    }
    atomic_init(&r->head, 0u);
    atomic_init(&r->tail, 0u);
    r->capacity = capacity;
    r->mask = capacity - 1u;
    r->slots = storage;
    return 0;
}

bool spsc_push(spsc_ring_t *r, const sensor_sample_t *s)
{
    uint32_t head = atomic_load_explicit(&r->head, memory_order_relaxed);
    uint32_t tail = atomic_load_explicit(&r->tail, memory_order_relaxed);

    if (ring_count(head, tail, r->capacity) >= r->capacity) {
        return false;
    }
    r->slots[head & r->mask] = *s;
    atomic_store_explicit(&r->head, head + 1u, memory_order_relaxed);
    return true;
}

bool spsc_pop(spsc_ring_t *r, sensor_sample_t *out)
{
    uint32_t tail = atomic_load_explicit(&r->tail, memory_order_relaxed);
    uint32_t head = atomic_load_explicit(&r->head, memory_order_relaxed);

    if (ring_count(head, tail, r->capacity) == 0u) {
        return false;
    }
    *out = r->slots[tail & r->mask];
    atomic_store_explicit(&r->tail, tail + 1u, memory_order_relaxed);
    return true;
}

uint32_t spsc_pop_batch(spsc_ring_t *r, sensor_sample_t *out, uint32_t max)
{
    uint32_t tail = atomic_load_explicit(&r->tail, memory_order_relaxed);
    uint32_t head = atomic_load_explicit(&r->head, memory_order_acquire);
    uint32_t n = ring_count(head, tail, r->capacity);

    if (n > max) {
        n = max;
    }
    if (n == 0u) {
        return 0u;
    }

    uint32_t start = tail & r->mask;
    uint32_t first = r->capacity - start; /* slots until the physical end */
    if (first >= n) {
        memcpy(out, &r->slots[start], (size_t)n * sizeof(*out));
    } else {
        memcpy(out, &r->slots[start], (size_t)first * sizeof(*out));
        memcpy(out + first, &r->slots[first], (size_t)(n - first) * sizeof(*out));
    }
    atomic_store_explicit(&r->tail, tail + n, memory_order_release);
    return n;
}

uint32_t spsc_size(const spsc_ring_t *r)
{
    uint32_t head = atomic_load_explicit(&((spsc_ring_t *)r)->head, memory_order_acquire);
    uint32_t tail = atomic_load_explicit(&((spsc_ring_t *)r)->tail, memory_order_acquire);
    return ring_count(head, tail, r->capacity);
}

uint32_t spsc_free(const spsc_ring_t *r)
{
    return r->capacity - spsc_size(r);
}

bool spsc_empty(const spsc_ring_t *r)
{
    return spsc_size(r) == 0u;
}

bool spsc_full(const spsc_ring_t *r)
{
    uint32_t head = atomic_load_explicit(&((spsc_ring_t *)r)->head, memory_order_acquire);
    uint32_t tail = atomic_load_explicit(&((spsc_ring_t *)r)->tail, memory_order_acquire);
    /* next write position would collide with the read position */
    return ((head + 1u) & r->mask) == (tail & r->mask);
}

void spsc_debug_set_counters(spsc_ring_t *r, uint32_t head, uint32_t tail)
{
    atomic_store_explicit(&r->head, head, memory_order_relaxed);
    atomic_store_explicit(&r->tail, tail, memory_order_relaxed);
}
