/* Host test double for the BLE HAL: records calls as text. */
#include <stdio.h>
#include <string.h>

#include "hal_ble.h"

#define STUB_BUF 4096

static char calls[STUB_BUF];
static size_t used;

static void rec(const char *fmt, unsigned a, unsigned b, int nargs)
{
    char item[64];
    if (nargs == 0) {
        snprintf(item, sizeof item, "%s", fmt);
    } else if (nargs == 1) {
        snprintf(item, sizeof item, fmt, a);
    } else {
        snprintf(item, sizeof item, fmt, a, b);
    }
    size_t n = strlen(item);
    if (used + n + 2 >= STUB_BUF) {
        return;
    }
    if (used > 0) {
        calls[used++] = ';';
    }
    memcpy(&calls[used], item, n);
    used += n;
    calls[used] = '\0';
}

void hal_stub_reset(void) { used = 0; calls[0] = '\0'; }
const char *hal_stub_calls(void) { return calls; }

void hal_adv_start(void) { rec("adv_start", 0, 0, 0); }
void hal_adv_stop(void) { rec("adv_stop", 0, 0, 0); }
void hal_mtu_reply(uint16_t mtu) { rec("mtu_reply:%u", mtu, 0, 1); }
void hal_pairing_start(void) { rec("pairing_start", 0, 0, 0); }
void hal_pairing_confirm(void) { rec("pairing_confirm", 0, 0, 0); }
void hal_pairing_failed(void) { rec("pairing_failed", 0, 0, 0); }
void hal_pairing_reject(void) { rec("pairing_reject", 0, 0, 0); }
void hal_enc_request(const uint8_t peer[6]) { rec("enc_request:%02x", peer[5], 0, 1); }
void hal_att_error(uint16_t handle, uint8_t att_err) { rec("att_error:0x%04x:%02x", handle, att_err, 2); }
void hal_att_write_rsp(uint16_t handle) { rec("att_write_rsp:0x%04x", handle, 0, 1); }
void hal_disconnect(uint8_t hci_reason) { rec("disconnect:0x%02x", hci_reason, 0, 1); }
void hal_link_reset(void) { rec("link_reset", 0, 0, 0); }
void hal_timer_arm(uint32_t ms) { rec("timer_arm:%u", (unsigned)ms, 0, 1); }
void hal_timer_cancel(void) { rec("timer_cancel", 0, 0, 0); }
