#include "bootcfg.h"

#include <string.h>

#include "crc32.h"

int bootcfg_tlv_next(const uint8_t *buf, size_t len, size_t *off, bootcfg_tlv_t *out)
{
    if (buf == NULL || off == NULL || out == NULL || *off > len) {
        return BOOTCFG_ERR_ARG;
    }
    while (*off < len && buf[*off] == BOOTCFG_T_PAD) {
        (*off)++;
    }
    if (*off == len) {
        return BOOTCFG_END;
    }

    size_t value_len = buf[*off + 1];
    int avail = (int)(len - *off - BOOTCFG_TLV_HDR);
    if (value_len > avail) {
        return BOOTCFG_ERR_TRUNCATED;
    }
    out->type = buf[*off];
    out->len = (uint8_t)value_len;
    out->value = &buf[*off + BOOTCFG_TLV_HDR];
    *off += BOOTCFG_TLV_HDR + value_len;
    return BOOTCFG_OK;
}

int bootcfg_tlv_put(uint8_t *buf, size_t cap, size_t *off, uint8_t type, const void *value, uint8_t len)
{
    if (buf == NULL || off == NULL || (len > 0 && value == NULL) || type == BOOTCFG_T_PAD) {
        return BOOTCFG_ERR_ARG;
    }
    if (*off > cap || cap - *off < BOOTCFG_TLV_HDR + (size_t)len) {
        return BOOTCFG_ERR_SPACE;
    }
    buf[*off] = type;
    buf[*off + 1] = len;
    if (len > 0) {
        memcpy(&buf[*off + BOOTCFG_TLV_HDR], value, len);
    }
    *off += BOOTCFG_TLV_HDR + len;
    return BOOTCFG_OK;
}

int bootcfg_seal(uint8_t *buf, size_t cap, size_t *off)
{
    if (buf == NULL || off == NULL) {
        return BOOTCFG_ERR_ARG;
    }
    uint32_t crc = crc32_ieee(buf, *off);
    uint8_t le[4] = {(uint8_t)crc, (uint8_t)(crc >> 8), (uint8_t)(crc >> 16), (uint8_t)(crc >> 24)};
    return bootcfg_tlv_put(buf, cap, off, BOOTCFG_T_CRC, le, 4);
}

int bootcfg_verify(const uint8_t *buf, size_t len)
{
    size_t off = 0, rec_start = 0;
    bootcfg_tlv_t rec;
    int rc;
    if (buf == NULL) {
        return BOOTCFG_ERR_ARG;
    }
    for (;;) {
        rec_start = off;
        rc = bootcfg_tlv_next(buf, len, &off, &rec);
        if (rc != BOOTCFG_OK) {
            return rc == BOOTCFG_END ? BOOTCFG_ERR_CRC : rc;
        }
        if (rec.type == BOOTCFG_T_CRC) {
            break;
        }
    }
    if (rec.len != 4 || off != len) {
        return BOOTCFG_ERR_CRC;
    }
    uint32_t stored = (uint32_t)rec.value[0] | ((uint32_t)rec.value[1] << 8) |
                      ((uint32_t)rec.value[2] << 16) | ((uint32_t)rec.value[3] << 24);
    /* PAD bytes before the CRC record are covered too: rec_start may be past them */
    while (rec_start < len && buf[rec_start] == BOOTCFG_T_PAD) {
        rec_start++;
    }
    return crc32_ieee(buf, rec_start) == stored ? BOOTCFG_OK : BOOTCFG_ERR_CRC;
}
