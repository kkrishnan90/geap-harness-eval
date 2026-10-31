#ifndef E2E_H
#define E2E_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* SAE J1850 CRC-8 (poly 0x1D, init 0xFF, xorout 0xFF), as used by AUTOSAR E2E P01. */
uint8_t crc8_sae_j1850(const uint8_t *data, size_t len);

typedef enum {
    ALIVE_OK = 0,
    ALIVE_INITIAL,      /* first frame seen */
    ALIVE_REPEATED,     /* same counter as last frame */
    ALIVE_OK_SOME_LOST, /* jump <= max_delta */
    ALIVE_WRONG_SEQ     /* jump > max_delta */
} alive_status_t;

typedef struct {
    bool seen;
    uint8_t last;
    uint8_t max_delta;  /* tolerated lost frames + 1 */
} alive_monitor_t;

void alive_init(alive_monitor_t *m, uint8_t max_delta);
/* counter is a 4-bit rolling counter (0..14 in E2E P01, 15 is invalid and wraps to 0). */
alive_status_t alive_check(alive_monitor_t *m, uint8_t counter);

#endif
