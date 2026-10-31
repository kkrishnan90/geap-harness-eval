/* Shared helpers for connection-manager tests. */
#ifndef CM_HELPERS_H
#define CM_HELPERS_H

#include <string.h>

#include "bond_store.h"
#include "conn_mgr.h"
#include "evt_log.h"
#include "hal_ble.h"

static const uint8_t PHONE_A[6] __attribute__((unused)) = {0x10, 0x20, 0x30, 0x40, 0x50, 0xA1};
static const uint8_t PHONE_B[6] __attribute__((unused)) = {0x11, 0x21, 0x31, 0x41, 0x51, 0xB2};

static inline cm_event_t ev_of(cm_event_type_t t)
{
    cm_event_t e;
    memset(&e, 0, sizeof e);
    e.type = t;
    return e;
}

static inline void send(cm_ctx_t *c, cm_event_type_t t)
{
    cm_event_t e = ev_of(t);
    cm_handle_event(c, &e);
}

static inline void send_status(cm_ctx_t *c, cm_event_type_t t, uint8_t status)
{
    cm_event_t e = ev_of(t);
    e.status = status;
    cm_handle_event(c, &e);
}

static inline void send_connect(cm_ctx_t *c, const uint8_t peer[6])
{
    cm_event_t e = ev_of(CM_EV_CONNECTED);
    memcpy(e.peer, peer, 6);
    cm_handle_event(c, &e);
}

static inline void send_mtu(cm_ctx_t *c, uint16_t mtu)
{
    cm_event_t e = ev_of(CM_EV_MTU_REQ);
    e.mtu = mtu;
    cm_handle_event(c, &e);
}

static inline void send_cccd(cm_ctx_t *c, uint16_t handle, uint16_t value)
{
    cm_event_t e = ev_of(CM_EV_CCCD_WRITE);
    e.handle = handle;
    e.value = value;
    cm_handle_event(c, &e);
}

static inline void fresh(cm_ctx_t *c)
{
    bond_store_clear();
    evt_log_clear();
    cm_init(c);
    hal_stub_reset();
}

#define CHECK_CALLS(expected) do { if (strcmp((expected), hal_stub_calls()) != 0) { \
    printf("  %s:%d: HAL calls\n    expected: %s\n    actual:   %s\n", __FILE__, __LINE__, (expected), hal_stub_calls()); \
    unit_failed_ = 1; } } while (0)

#endif
