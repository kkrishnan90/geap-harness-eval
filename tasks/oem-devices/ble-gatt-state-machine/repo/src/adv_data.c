#include "adv_data.h"

#include <string.h>

void adv_init(adv_payload_t *p)
{
    memset(p, 0, sizeof *p);
}

int adv_add(adv_payload_t *p, uint8_t ad_type, const void *value, size_t len)
{
    if (p->len + 2u + len > ADV_MAX_LEN || len > 29u) {
        return -1;
    }
    p->data[p->len++] = (uint8_t)(len + 1u);
    p->data[p->len++] = ad_type;
    if (len > 0u) {
        memcpy(&p->data[p->len], value, len);
    }
    p->len += len;
    return 0;
}

int adv_build_key_service(adv_payload_t *p, const char *name, uint16_t service_uuid)
{
    const uint8_t flags = 0x06u; /* LE General Discoverable, BR/EDR not supported */
    const uint8_t uuid[2] = {(uint8_t)(service_uuid & 0xFFu), (uint8_t)(service_uuid >> 8)};
    adv_init(p);
    if (adv_add(p, AD_TYPE_FLAGS, &flags, 1) != 0 || adv_add(p, AD_TYPE_UUID16_COMPLETE, uuid, 2) != 0) {
        return -1;
    }
    size_t room = ADV_MAX_LEN - p->len - 2u;
    size_t n = strlen(name);
    if (n <= room) {
        return adv_add(p, AD_TYPE_NAME_COMPLETE, name, n);
    }
    return adv_add(p, AD_TYPE_NAME_SHORT, name, room);
}
