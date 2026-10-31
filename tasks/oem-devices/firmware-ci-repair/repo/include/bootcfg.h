#ifndef BOOTCFG_H
#define BOOTCFG_H

#include <stddef.h>
#include <stdint.h>

#define BOOTCFG_OK 0
#define BOOTCFG_END 1               /* no more records */
#define BOOTCFG_ERR_ARG (-1)
#define BOOTCFG_ERR_TRUNCATED (-2)  /* record header or value runs past the buffer */
#define BOOTCFG_ERR_SPACE (-3)      /* output buffer too small */
#define BOOTCFG_ERR_CRC (-4)

/* Record types used by the stage-2 bootloader. */
enum bootcfg_type {
    BOOTCFG_T_PAD = 0x00,          /* single byte, no length */
    BOOTCFG_T_ACTIVE_SLOT = 0x01,  /* 1 byte: 0 = A, 1 = B */
    BOOTCFG_T_BOOT_COUNT = 0x02,   /* 4 bytes LE */
    BOOTCFG_T_FW_VERSION = 0x10,   /* ASCII, not NUL terminated */
    BOOTCFG_T_SERIAL = 0x11,       /* ASCII */
    BOOTCFG_T_CRC = 0xFE           /* 4 bytes LE, CRC-32 over all preceding bytes; last record */
};

/* Record layout: type (1 byte), length (1 byte), value (length bytes). PAD has no length. */
#define BOOTCFG_TLV_HDR 2u

typedef struct {
    uint8_t type;
    uint8_t len;
    const uint8_t *value; /* points into the input buffer */
} bootcfg_tlv_t;

/* Decodes the record at *off and advances *off past it. PAD bytes are skipped.
 * Returns BOOTCFG_OK, BOOTCFG_END when *off == len, or an error. */
int bootcfg_tlv_next(const uint8_t *buf, size_t len, size_t *off, bootcfg_tlv_t *out);

/* Appends a record at *off. Returns BOOTCFG_OK or BOOTCFG_ERR_SPACE / BOOTCFG_ERR_ARG. */
int bootcfg_tlv_put(uint8_t *buf, size_t cap, size_t *off, uint8_t type, const void *value, uint8_t len);

/* Appends the CRC record over buf[0 .. *off). */
int bootcfg_seal(uint8_t *buf, size_t cap, size_t *off);

/* Verifies that the block ends with a CRC record matching the preceding bytes. */
int bootcfg_verify(const uint8_t *buf, size_t len);

#endif
