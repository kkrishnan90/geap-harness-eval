#ifndef IMU_FRAME_H
#define IMU_FRAME_H

#include <stddef.h>
#include <stdint.h>

#include "sample.h"

/* IPC frame to the application processor (little endian on the wire):
 *   [0]     0xA5 sync
 *   [1]     sample count n (1..IMU_FRAME_MAX_SAMPLES)
 *   [2..5]  timestamp_us of the first sample
 *   then n * 12 bytes: accel x,y,z, gyro x,y,z (int16 LE)
 *   then CRC-16/CCITT-FALSE over bytes [0 .. end of samples) (LE)
 */
#define IMU_FRAME_SIZE 64u
#define IMU_FRAME_MAX_SAMPLES 4u

uint16_t crc16_ccitt_false(const uint8_t *data, size_t len);

/* Returns the number of bytes written (<= IMU_FRAME_SIZE) or 0 on bad arguments. */
size_t imu_frame_pack(const sensor_sample_t *samples, uint32_t n, uint8_t out[IMU_FRAME_SIZE]);

/* Returns sample count, or -1 on sync/length/CRC error. Timestamps after the first are 0. */
int imu_frame_unpack(const uint8_t *frame, size_t len, sensor_sample_t *samples, uint32_t max);

#endif
