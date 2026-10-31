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
    if (sig->start_bit >= (unsigned)dlc * 8u) {
        return CAN_ERR_RANGE;
    }
    if (sig->order == CAN_LITTLE_ENDIAN) {
        if ((unsigned)sig->start_bit + sig->length > (unsigned)dlc * 8u) {
            return CAN_ERR_RANGE;
        }
    } else {
        /* Motorola: the LSB lies (length - 1) positions further in the sawtooth order. */
        unsigned msb_byte = sig->start_bit / 8u;
        unsigned bits_in_first = sig->start_bit % 8u + 1u;
        unsigned extra_bytes = 0;
        if (sig->length > bits_in_first) {
            extra_bytes = (sig->length - bits_in_first + 7u) / 8u;
        }
        if (msb_byte + extra_bytes >= dlc) {
            return CAN_ERR_RANGE;
        }
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
        /* Motorola: walk from the MSB towards the LSB; after bit 0 of a byte
         * continue with bit 7 of the next byte. */
        unsigned pos = sig->start_bit;
        for (unsigned i = 0; i < sig->length; i++) {
            v = (v << 1) | bit_at(data, pos);
            if (pos % 8u == 0u) {
                pos += 15u;
            } else {
                pos--;
            }
        }
    }
    *raw = v;
    return CAN_OK;
}

static int64_t sign_extend(uint64_t raw, unsigned length)
{
    if (length >= 64u) {
        return (int64_t)raw;
    }
    uint64_t sign = (uint64_t)1 << (length - 1u);
    if (raw & sign) {
        /* two's complement: set every bit above the signal */
        return (int64_t)(raw | ~((sign << 1) - 1u));
    }
    return (int64_t)raw;
}

int can_decode_value(const uint8_t *data, uint8_t dlc, const can_signal_t *sig, int64_t *value)
{
    uint64_t raw;
    int rc = can_extract_raw(data, dlc, sig, &raw);
    if (rc != CAN_OK) {
        return rc;
    }
    *value = sig->is_signed ? sign_extend(raw, sig->length) : (int64_t)raw;
    return CAN_OK;
}

int can_decode_physical(const uint8_t *data, uint8_t dlc, const can_signal_t *sig, double *phys)
{
    uint64_t raw;
    int rc = can_extract_raw(data, dlc, sig, &raw);
    if (rc != CAN_OK) {
        return rc;
    }
    double v = sig->is_signed ? (double)sign_extend(raw, sig->length) : (double)raw;
    *phys = v * sig->factor + sig->offset;
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
