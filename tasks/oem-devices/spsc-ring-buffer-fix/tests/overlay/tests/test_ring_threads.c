/* Producer/consumer on two threads, starting just before the uint32 counter wrap.
 * Bounded: each side gives up after a spin budget, so a broken ring fails instead of hanging. */
#include <pthread.h>
#include <sched.h>

#include "spsc_ring.h"
#include "unit.h"

#define CAP 64u
#define ITEMS 200000u
#define SPIN_BUDGET 400000000ull

static sensor_sample_t storage[CAP];
static spsc_ring_t ring;
static volatile int producer_gave_up;

static void *producer(void *arg)
{
    (void)arg;
    unsigned long long spins = 0;
    for (uint32_t i = 0; i < ITEMS; i++) {
        sensor_sample_t s = {0};
        s.seq = i;
        s.timestamp_us = i * 7u + 1u;
        s.accel[0] = (int16_t)(i & 0x7FFF);
        s.gyro[0] = (int16_t)~(i & 0x7FFF);
        while (!spsc_push(&ring, &s)) {
            if (++spins > SPIN_BUDGET) {
                producer_gave_up = 1;
                return NULL;
            }
            if ((spins & 1023u) == 0u) sched_yield();
        }
    }
    return NULL;
}

static int run_round(uint32_t start, uint32_t batch_max)
{
    spsc_init(&ring, storage, CAP);
    spsc_debug_set_counters(&ring, start, start);
    producer_gave_up = 0;
    pthread_t th;
    pthread_create(&th, NULL, producer, NULL);

    sensor_sample_t out[CAP];
    uint32_t expected = 0;
    int ok = 1;
    unsigned long long spins = 0;
    while (expected < ITEMS && ok) {
        uint32_t n = batch_max == 1u ? (spsc_pop(&ring, &out[0]) ? 1u : 0u)
                                     : spsc_pop_batch(&ring, out, batch_max);
        if (n == 0u) {
            if (++spins > SPIN_BUDGET || producer_gave_up) {
                printf("  stalled at %u (start 0x%08x)\n", expected, start);
                ok = 0;
            }
            if ((spins & 1023u) == 0u) sched_yield();
            continue;
        }
        for (uint32_t k = 0; k < n; k++, expected++) {
            sensor_sample_t *s = &out[k];
            if (expected >= ITEMS || s->seq != expected || s->timestamp_us != expected * 7u + 1u ||
                s->accel[0] != (int16_t)(expected & 0x7FFF) || s->gyro[0] != (int16_t)~(expected & 0x7FFF)) {
                printf("  corrupt sample at %u: seq=%u (start 0x%08x)\n", expected, s->seq, start);
                ok = 0;
                break;
            }
        }
    }
    if (!ok) {
        /* unblock the producer so it can be joined */
        spsc_debug_set_counters(&ring, 0u, 0u);
    }
    pthread_join(th, NULL);
    if (ok && !spsc_empty(&ring)) {
        printf("  ring not empty after all items consumed\n");
        ok = 0;
    }
    return ok && !producer_gave_up;
}

TEST(stream_across_wrap)
{
    /* rounds alternate single pops and batch reads of different sizes */
    static const uint32_t batches[] = {1u, 64u, 17u, 1u, 5u, 64u, 33u, 1u, 64u};
    for (uint32_t r = 0; r < 9; r++) {
        CHECK(run_round(0xFFFFFFFFu - 30000u - r * 31u, batches[r]));
    }
}

int main(void)
{
    RUN("threads", stream_across_wrap);
    UNIT_EXIT();
}
