#ifndef HAL_BLE_H
#define HAL_BLE_H

/* Platform abstraction over the vendor BLE controller/host stack.
 * Target build: src/port/<soc>/hal_ble_<soc>.c (vendor repo).
 * Host build:   src/hal_ble_stub.c records every call for the unit tests. */

#include <stdint.h>

void hal_adv_start(void);
void hal_adv_stop(void);
void hal_mtu_reply(uint16_t mtu);
void hal_pairing_start(void);     /* shows the passkey on the cluster display */
void hal_pairing_confirm(void);
void hal_pairing_failed(void);
void hal_pairing_reject(void);    /* SMP "pairing not supported/too many attempts" */
void hal_enc_request(const uint8_t peer[6]); /* start encryption with the stored LTK */
void hal_att_error(uint16_t handle, uint8_t att_err);
void hal_att_write_rsp(uint16_t handle);
void hal_disconnect(uint8_t hci_reason);
void hal_link_reset(void);        /* force-drop the link at controller level */
void hal_timer_arm(uint32_t ms);  /* single connection-supervision timer */
void hal_timer_cancel(void);

/* ---- host stub only ---- */
void hal_stub_reset(void);
/* All calls since the last reset, ';'-separated, e.g. "adv_start;timer_arm:30000". */
const char *hal_stub_calls(void);

#endif
