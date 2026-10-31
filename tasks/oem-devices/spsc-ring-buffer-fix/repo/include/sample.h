#ifndef SAMPLE_H
#define SAMPLE_H

#include <stdint.h>

/* One IMU sample as delivered by the BMI270 driver (raw LSB units). */
typedef struct {
    uint32_t timestamp_us; /* sensor-hub monotonic clock */
    uint32_t seq;          /* driver sequence number */
    int16_t accel[3];
    int16_t gyro[3];
} sensor_sample_t;

#endif
