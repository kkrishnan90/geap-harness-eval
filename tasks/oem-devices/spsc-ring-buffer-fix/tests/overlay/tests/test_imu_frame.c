#include <string.h>

#include "imu_frame.h"
#include "unit.h"

TEST(crc_check_value)
{
    CHECK_EQ_INT(0x29B1, crc16_ccitt_false((const uint8_t *)"123456789", 9));
}

TEST(roundtrip)
{
    sensor_sample_t in[3] = {{0}}, out[4];
    for (int i = 0; i < 3; i++) {
        in[i].timestamp_us = 123456u + (uint32_t)i;
        in[i].accel[0] = (int16_t)(100 * i - 150);
        in[i].accel[2] = -32768;
        in[i].gyro[1] = 32767;
    }
    uint8_t frame[IMU_FRAME_SIZE];
    size_t n = imu_frame_pack(in, 3, frame);
    CHECK_EQ_INT(6 + 36 + 2, n);
    CHECK_EQ_INT(3, imu_frame_unpack(frame, n, out, 4));
    CHECK_EQ_INT(123456, out[0].timestamp_us);
    CHECK_EQ_INT(50, out[2].accel[0]);
    CHECK_EQ_INT(-32768, out[1].accel[2]);
    CHECK_EQ_INT(32767, out[2].gyro[1]);
}

TEST(corruption_detected)
{
    sensor_sample_t in[1] = {{0}}, out[4];
    in[0].accel[1] = 42;
    uint8_t frame[IMU_FRAME_SIZE];
    size_t n = imu_frame_pack(in, 1, frame);
    frame[8] ^= 0x01u;
    CHECK_EQ_INT(-1, imu_frame_unpack(frame, n, out, 4));
}

TEST(bad_arguments)
{
    sensor_sample_t in[5] = {{0}};
    uint8_t frame[IMU_FRAME_SIZE];
    CHECK_EQ_INT(0, imu_frame_pack(in, 0, frame));
    CHECK_EQ_INT(0, imu_frame_pack(in, 5, frame));
}

int main(void)
{
    RUN("frame", crc_check_value);
    RUN("frame", roundtrip);
    RUN("frame", corruption_detected);
    RUN("frame", bad_arguments);
    UNIT_EXIT();
}
