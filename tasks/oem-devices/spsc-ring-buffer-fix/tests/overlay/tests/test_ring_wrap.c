#include "spsc_ring.h"
#include "unit.h"

static sensor_sample_t mk(uint32_t seq)
{
    sensor_sample_t s = {0};
    s.seq = seq;
    s.accel[1] = (int16_t)(seq * 3u);
    return s;
}

/* ---- capacity / full-empty ---- */

TEST(fills_every_slot)
{
    sensor_sample_t buf[8];
    spsc_ring_t r;
    spsc_init(&r, buf, 8);
    for (uint32_t i = 0; i < 7; i++) {
        sensor_sample_t s = mk(i);
        CHECK(spsc_push(&r, &s));
    }
    CHECK(!spsc_full(&r));
    sensor_sample_t s = mk(7);
    CHECK(spsc_push(&r, &s));
    CHECK(spsc_full(&r));
    CHECK(!spsc_empty(&r));
    CHECK_EQ_INT(8, spsc_size(&r));
    CHECK_EQ_INT(0, spsc_free(&r));
    sensor_sample_t extra = mk(99);
    CHECK(!spsc_push(&r, &extra));
    CHECK_EQ_INT(8, spsc_size(&r));
}

TEST(full_two_slot_ring)
{
    sensor_sample_t buf[2];
    spsc_ring_t r;
    spsc_init(&r, buf, 2);
    sensor_sample_t a = mk(1), b = mk(2), c = mk(3), out;
    CHECK(spsc_push(&r, &a));
    CHECK(!spsc_full(&r));
    CHECK(spsc_push(&r, &b));
    CHECK(spsc_full(&r));
    CHECK(!spsc_push(&r, &c));
    CHECK(spsc_pop(&r, &out));
    CHECK_EQ_INT(1, out.seq);
    CHECK(spsc_push(&r, &c));
    CHECK(spsc_pop(&r, &out));
    CHECK_EQ_INT(2, out.seq);
    CHECK(spsc_pop(&r, &out));
    CHECK_EQ_INT(3, out.seq);
    CHECK(spsc_empty(&r));
}

/* ---- uint32 counter wraparound ---- */

TEST(size_when_head_wrapped)
{
    sensor_sample_t buf[16];
    spsc_ring_t r;
    spsc_init(&r, buf, 16);
    spsc_debug_set_counters(&r, 3u, 0xFFFFFFFBu); /* 5 before the wrap + 3 after */
    CHECK_EQ_INT(8, spsc_size(&r));
    CHECK_EQ_INT(8, spsc_free(&r));
    CHECK(!spsc_full(&r));
    CHECK(!spsc_empty(&r));
    spsc_debug_set_counters(&r, 0x0000000Au, 0xFFFFFFFAu); /* exactly 16 */
    CHECK(spsc_full(&r));
    CHECK_EQ_INT(16, spsc_size(&r));
}

TEST(push_pop_across_wrap)
{
    sensor_sample_t buf[8];
    spsc_ring_t r;
    spsc_init(&r, buf, 8);
    spsc_debug_set_counters(&r, 0xFFFFFFFDu, 0xFFFFFFFDu);
    CHECK(spsc_empty(&r));
    for (uint32_t i = 0; i < 8; i++) {
        sensor_sample_t s = mk(i);
        CHECK(spsc_push(&r, &s));
    }
    CHECK(spsc_full(&r));
    for (uint32_t i = 0; i < 8; i++) {
        sensor_sample_t out = mk(0xDEAD);
        CHECK(spsc_pop(&r, &out));
        CHECK_EQ_INT(i, out.seq);
        CHECK_EQ_INT((int16_t)(i * 3u), out.accel[1]);
    }
    CHECK(spsc_empty(&r));
}

TEST(steady_stream_through_wrap)
{
    sensor_sample_t buf[4];
    spsc_ring_t r;
    spsc_init(&r, buf, 4);
    spsc_debug_set_counters(&r, 0xFFFFFFF0u, 0xFFFFFFF0u);
    uint32_t next_in = 0, next_out = 0;
    for (int round = 0; round < 40; round++) {
        while (!spsc_full(&r)) {
            sensor_sample_t s = mk(next_in++);
            CHECK(spsc_push(&r, &s));
            if (next_in > 1000u) break;
        }
        for (int k = 0; k < 3; k++) {
            sensor_sample_t out;
            CHECK(spsc_pop(&r, &out));
            CHECK_EQ_INT(next_out, out.seq);
            next_out++;
        }
    }
    CHECK(next_in >= 120u);
}

/* ---- batch read crossing the physical end of the array ---- */

TEST(batch_across_array_end)
{
    sensor_sample_t buf[8], out[8];
    spsc_ring_t r;
    spsc_init(&r, buf, 8);
    for (uint32_t i = 0; i < 6; i++) {
        sensor_sample_t s = mk(i), o;
        spsc_push(&r, &s);
        spsc_pop(&r, &o);
    }
    for (uint32_t i = 0; i < 6; i++) {
        sensor_sample_t s = mk(100u + i);
        CHECK(spsc_push(&r, &s)); /* slots 6,7,0,1,2,3 */
    }
    CHECK_EQ_INT(6, spsc_pop_batch(&r, out, 8));
    for (uint32_t i = 0; i < 6; i++) {
        CHECK_EQ_INT(100u + i, out[i].seq);
    }
    CHECK(spsc_empty(&r));
}

TEST(batch_limited_by_max_across_end)
{
    sensor_sample_t buf[8], out[8];
    spsc_ring_t r;
    spsc_init(&r, buf, 8);
    spsc_debug_set_counters(&r, 5u, 5u);
    for (uint32_t i = 0; i < 8; i++) {
        sensor_sample_t s = mk(200u + i);
        CHECK(spsc_push(&r, &s));
    }
    CHECK_EQ_INT(5, spsc_pop_batch(&r, out, 5));
    for (uint32_t i = 0; i < 5; i++) {
        CHECK_EQ_INT(200u + i, out[i].seq);
    }
    CHECK_EQ_INT(3, spsc_pop_batch(&r, out, 8));
    for (uint32_t i = 0; i < 3; i++) {
        CHECK_EQ_INT(205u + i, out[i].seq);
    }
}

TEST(batch_across_counter_wrap)
{
    sensor_sample_t buf[16], out[16];
    spsc_ring_t r;
    spsc_init(&r, buf, 16);
    spsc_debug_set_counters(&r, 0xFFFFFFF9u, 0xFFFFFFF9u);
    for (uint32_t i = 0; i < 10; i++) {
        sensor_sample_t s = mk(i);
        CHECK(spsc_push(&r, &s));
    }
    CHECK_EQ_INT(10, spsc_size(&r));
    CHECK_EQ_INT(10, spsc_pop_batch(&r, out, 16));
    for (uint32_t i = 0; i < 10; i++) {
        CHECK_EQ_INT(i, out[i].seq);
    }
    CHECK(spsc_empty(&r));
    CHECK_EQ_INT(0, spsc_pop_batch(&r, out, 16));
}

/* ---- regression guards (behaviour that must not change) ---- */

TEST(empty_after_init)
{
    sensor_sample_t buf[32];
    spsc_ring_t r;
    spsc_init(&r, buf, 32);
    CHECK(spsc_empty(&r));
    CHECK(!spsc_full(&r));
    CHECK_EQ_INT(32, spsc_free(&r));
}

TEST(max_capacity_accepted)
{
    spsc_ring_t r;
    sensor_sample_t dummy;
    CHECK_EQ_INT(0, spsc_init(&r, &dummy, 0x80000000u));
    CHECK_EQ_INT(-1, spsc_init(&r, &dummy, 0x80000001u));
    CHECK_EQ_INT(-1, spsc_init(&r, &dummy, 0xFFFFFFFFu));
}

int main(void)
{
    RUN("wrap", fills_every_slot);
    RUN("wrap", full_two_slot_ring);
    RUN("wrap", size_when_head_wrapped);
    RUN("wrap", push_pop_across_wrap);
    RUN("wrap", steady_stream_through_wrap);
    RUN("wrap", batch_across_array_end);
    RUN("wrap", batch_limited_by_max_across_end);
    RUN("wrap", batch_across_counter_wrap);
    RUN("wrap", empty_after_init);
    RUN("wrap", max_capacity_accepted);
    UNIT_EXIT();
}
