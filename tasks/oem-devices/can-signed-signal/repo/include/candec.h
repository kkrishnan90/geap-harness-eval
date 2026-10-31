#ifndef CANDEC_H
#define CANDEC_H

#include <stdbool.h>
#include <stdint.h>

#define CAN_OK          0
#define CAN_ERR_NULL   (-1) /* NULL data / signal / output pointer */
#define CAN_ERR_LENGTH (-2) /* signal length 0 or > 64 */
#define CAN_ERR_RANGE  (-3) /* signal does not fit inside the first dlc bytes */
#define CAN_ERR_DLC    (-4) /* dlc > 8 (classic CAN) */

typedef enum {
    CAN_BIG_ENDIAN = 0,    /* DBC @0, Motorola: start_bit = MSB position */
    CAN_LITTLE_ENDIAN = 1  /* DBC @1, Intel:    start_bit = LSB position */
} can_byte_order_t;

typedef struct {
    const char *name;
    uint8_t start_bit;
    uint8_t length;          /* 1..64 */
    can_byte_order_t order;
    bool is_signed;          /* two's complement of `length` bits */
    double factor;
    double offset;
} can_signal_t;

/* Raw, unsigned bit pattern of the signal (right-aligned). */
int can_extract_raw(const uint8_t *data, uint8_t dlc, const can_signal_t *sig, uint64_t *raw);

/* Integer value: sign-extended when sig->is_signed. */
int can_decode_value(const uint8_t *data, uint8_t dlc, const can_signal_t *sig, int64_t *value);

/* Physical value = value * factor + offset (value is signed when sig->is_signed). */
int can_decode_physical(const uint8_t *data, uint8_t dlc, const can_signal_t *sig, double *phys);

const char *can_strerror(int err);

#endif
