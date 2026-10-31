#include "candec.h"

#include <stddef.h>

static int check_args(const uint8_t *data, uint8_t dlc, const can_signal_t *sig, const void *out)
{
    if (data == NULL || sig == NULL || out == NULL) {
        return CAN_ERR_NULL;
    }
    if (dlc > 8) {
        return CAN_ERR_DLC;
    }
    if (sig->length == 0 || sig->length > 64) {
        return CAN_ERR_LENGTH;
    }
    if ((unsigned)sig->start_bit + sig->length > (unsigned)dlc * 8u) {
        return CAN_ERR_RANGE;
    }
    return CAN_OK;
}

static inline unsigned bit_at(const uint8_t *data, unsigned pos)
{
    return (data[pos / 8u] >> (pos % 8u)) & 1u;
}

int can_extract_raw(const uint8_t *data, uint8_t dlc, const can_signal_t *sig, uint64_t *raw)
{
    int rc = check_args(data, dlc, sig, raw);
    if (rc != CAN_OK) {
        return rc;
    }

    uint64_t v = 0;
    if (sig->order == CAN_LITTLE_ENDIAN) {
        for (unsigned i = 0; i < sig->length; i++) {
            v |= (uint64_t)bit_at(data, sig->start_bit + i) << i;
        }
    } else {
        /* Motorola: walk from the MSB towards the LSB. */
        unsigned pos = sig->start_bit;
        for (unsigned i = 0; i < sig->length; i++) {
            v = (v << 1) | bit_at(data, pos);
            if (pos % 8u == 0u) {
                pos += 8u;
            } else {
                pos--;
            }
        }
    }
    *raw = v;
    return CAN_OK;
}

int can_decode_value(const uint8_t *data, uint8_t dlc, const can_signal_t *sig, int64_t *value)
{
    uint64_t raw;
    int rc = can_extract_raw(data, dlc, sig, &raw);
    if (rc != CAN_OK) {
        return rc;
    }
    if (sig->is_signed && sig->length <= 32) {
        unsigned shift = 32u - sig->length;
        *value = (int64_t)((int32_t)((uint32_t)raw << shift) >> shift);
    } else {
        *value = (int64_t)raw;
    }
    return CAN_OK;
}

int can_decode_physical(const uint8_t *data, uint8_t dlc, const can_signal_t *sig, double *phys)
{
    uint64_t raw;
    int rc = can_extract_raw(data, dlc, sig, &raw);
    if (rc != CAN_OK) {
        return rc;
    }
    *phys = (double)raw * sig->factor + sig->offset;
    return CAN_OK;
}

const char *can_strerror(int err)
{
    switch (err) {
    case CAN_OK:         return "ok";
    case CAN_ERR_NULL:   return "null argument";
    case CAN_ERR_LENGTH: return "invalid signal length";
    case CAN_ERR_RANGE:  return "signal outside frame payload";
    case CAN_ERR_DLC:    return "invalid dlc";
    default:             return "unknown error";
    }
}
