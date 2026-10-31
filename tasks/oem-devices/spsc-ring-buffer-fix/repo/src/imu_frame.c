#include "imu_frame.h"

#include <string.h>

uint16_t crc16_ccitt_false(const uint8_t *data, size_t len)
{
    uint16_t crc = 0xFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint16_t)((uint16_t)data[i] << 8);
        for (int b = 0; b < 8; b++) {
            crc = (crc & 0x8000u) ? (uint16_t)((crc << 1) ^ 0x1021u) : (uint16_t)(crc << 1);
        }
    }
    return crc;
}

static void put16(uint8_t *p, int16_t v)
{
    uint16_t u = (uint16_t)v;
    p[0] = (uint8_t)(u & 0xFFu);
    p[1] = (uint8_t)(u >> 8);
}

static int16_t get16(const uint8_t *p)
{
    return (int16_t)(uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

size_t imu_frame_pack(const sensor_sample_t *samples, uint32_t n, uint8_t out[IMU_FRAME_SIZE])
{
    if (samples == NULL || out == NULL || n == 0u || n > IMU_FRAME_MAX_SAMPLES) {
        return 0u;
    }
    size_t pos = 0;
    out[pos++] = 0xA5u;
    out[pos++] = (uint8_t)n;
    uint32_t ts = samples[0].timestamp_us;
    for (int i = 0; i < 4; i++) {
        out[pos++] = (uint8_t)(ts >> (8 * i));
    }
    for (uint32_t s = 0; s < n; s++) {
        for (int a = 0; a < 3; a++) {
            put16(&out[pos], samples[s].accel[a]);
            pos += 2;
        }
        for (int g = 0; g < 3; g++) {
            put16(&out[pos], samples[s].gyro[g]);
            pos += 2;
        }
    }
    uint16_t crc = crc16_ccitt_false(out, pos);
    out[pos++] = (uint8_t)(crc & 0xFFu);
    out[pos++] = (uint8_t)(crc >> 8);
    return pos;
}

int imu_frame_unpack(const uint8_t *frame, size_t len, sensor_sample_t *samples, uint32_t max)
{
    if (frame == NULL || samples == NULL || len < 8u || frame[0] != 0xA5u) {
        return -1;
    }
    uint32_t n = frame[1];
    size_t body = 6u + (size_t)n * 12u;
    if (n == 0u || n > IMU_FRAME_MAX_SAMPLES || n > max || len < body + 2u) {
        return -1;
    }
    uint16_t crc = (uint16_t)(frame[body] | (frame[body + 1] << 8));
    if (crc != crc16_ccitt_false(frame, body)) {
        return -1;
    }
    memset(samples, 0, (size_t)n * sizeof(*samples));
    samples[0].timestamp_us = (uint32_t)frame[2] | ((uint32_t)frame[3] << 8) |
                              ((uint32_t)frame[4] << 16) | ((uint32_t)frame[5] << 24);
    size_t pos = 6;
    for (uint32_t s = 0; s < n; s++) {
        for (int a = 0; a < 3; a++, pos += 2) {
            samples[s].accel[a] = get16(&frame[pos]);
        }
        for (int g = 0; g < 3; g++, pos += 2) {
            samples[s].gyro[g] = get16(&frame[pos]);
        }
    }
    return (int)n;
}
