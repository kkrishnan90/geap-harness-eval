#include "spsc_ring.h"
#include "unit.h"

static sensor_sample_t mk(uint32_t seq)
{
    sensor_sample_t s = {0};
    s.seq = seq;
    s.timestamp_us = seq * 100u;
    s.accel[0] = (int16_t)seq;
    s.gyro[2] = (int16_t)(-(int32_t)seq);
    return s;
}

TEST(init_validates_capacity)
{
    sensor_sample_t buf[16];
    spsc_ring_t r;
    CHECK_EQ_INT(0, spsc_init(&r, buf, 16));
    CHECK_EQ_INT(-1, spsc_init(&r, buf, 12));
    CHECK_EQ_INT(-1, spsc_init(&r, buf, 1));
    CHECK_EQ_INT(-1, spsc_init(&r, buf, 0));
    CHECK_EQ_INT(-1, spsc_init(&r, NULL, 16));
    CHECK_EQ_INT(-1, spsc_init(NULL, buf, 16));
}

TEST(fifo_order)
{
    sensor_sample_t buf[8];
    spsc_ring_t r;
    spsc_init(&r, buf, 8);
    for (uint32_t i = 0; i < 5; i++) {
        sensor_sample_t s = mk(i);
        CHECK(spsc_push(&r, &s));
    }
    CHECK_EQ_INT(5, spsc_size(&r));
    for (uint32_t i = 0; i < 5; i++) {
        sensor_sample_t out;
        CHECK(spsc_pop(&r, &out));
        CHECK_EQ_INT(i, out.seq);
        CHECK_EQ_INT(-(int)i, out.gyro[2]);
    }
    CHECK(spsc_empty(&r));
}

TEST(pop_empty_leaves_output)
{
    sensor_sample_t buf[4];
    spsc_ring_t r;
    spsc_init(&r, buf, 4);
    sensor_sample_t out = mk(77);
    CHECK(!spsc_pop(&r, &out));
    CHECK_EQ_INT(77, out.seq);
    CHECK_EQ_INT(0, spsc_pop_batch(&r, &out, 4));
}

TEST(batch_within_array)
{
    sensor_sample_t buf[8], out[8];
    spsc_ring_t r;
    spsc_init(&r, buf, 8);
    for (uint32_t i = 0; i < 6; i++) {
        sensor_sample_t s = mk(i);
        spsc_push(&r, &s);
    }
    CHECK_EQ_INT(4, spsc_pop_batch(&r, out, 4));
    for (uint32_t i = 0; i < 4; i++) {
        CHECK_EQ_INT(i, out[i].seq);
    }
    CHECK_EQ_INT(2, spsc_size(&r));
    CHECK_EQ_INT(6, spsc_free(&r));
}

TEST(interleaved_small_lap)
{
    sensor_sample_t buf[4];
    spsc_ring_t r;
    spsc_init(&r, buf, 4);
    uint32_t next_in = 0, next_out = 0;
    for (int round = 0; round < 50; round++) {
        for (int k = 0; k < 3; k++) {
            sensor_sample_t s = mk(next_in++);
            CHECK(spsc_push(&r, &s));
        }
        for (int k = 0; k < 3; k++) {
            sensor_sample_t out;
            CHECK(spsc_pop(&r, &out));
            CHECK_EQ_INT(next_out, out.seq);
            next_out++;
        }
    }
}

int main(void)
{
    RUN("ring", init_validates_capacity);
    RUN("ring", fifo_order);
    RUN("ring", pop_empty_leaves_output);
    RUN("ring", batch_within_array);
    RUN("ring", interleaved_small_lap);
    UNIT_EXIT();
}
