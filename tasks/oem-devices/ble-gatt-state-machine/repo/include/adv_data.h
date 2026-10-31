#ifndef ADV_DATA_H
#define ADV_DATA_H

/* Advertising payload builder (AD structures, Core Spec Vol 3 Part C §11). */

#include <stddef.h>
#include <stdint.h>

#define ADV_MAX_LEN 31u

typedef struct {
    uint8_t data[ADV_MAX_LEN];
    size_t len;
} adv_payload_t;

void adv_init(adv_payload_t *p);
/* Appends one AD structure (length, type, value). Returns 0, or -1 if it does not fit. */
int adv_add(adv_payload_t *p, uint8_t ad_type, const void *value, size_t len);
/* Flags + complete local name (shortened name if it does not fit) + 16-bit service UUID. */
int adv_build_key_service(adv_payload_t *p, const char *name, uint16_t service_uuid);

#define AD_TYPE_FLAGS 0x01u
#define AD_TYPE_UUID16_COMPLETE 0x03u
#define AD_TYPE_NAME_SHORT 0x08u
#define AD_TYPE_NAME_COMPLETE 0x09u

#endif
