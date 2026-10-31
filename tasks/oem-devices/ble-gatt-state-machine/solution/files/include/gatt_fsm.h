#ifndef GATT_FSM_H
#define GATT_FSM_H

/* Table-driven connection state machine (design: docs/conn_fsm.md).
 * conn_mgr.c is a thin facade over gfsm_dispatch(). */

#include <stdbool.h>
#include <stddef.h>

#include "conn_mgr.h"

typedef enum {
    GFSM_GUARD_NONE = 0,
    GFSM_GUARD_PEER_BONDED,
    GFSM_GUARD_PAIR_ATTEMPTS_LEFT,
    GFSM_GUARD_STATUS_OK,
    GFSM_GUARD_CCCD_ENABLE,
    GFSM_GUARD_COUNT
} gfsm_guard_t;

typedef enum {
    GFSM_ACT_NONE = 0,
    GFSM_ACT_ADV_START,
    GFSM_ACT_ADV_STOP,
    GFSM_ACT_CONNECT_NEW,
    GFSM_ACT_CONNECT_BONDED,
    GFSM_ACT_MTU_REPLY,
    GFSM_ACT_PAIR_START,
    GFSM_ACT_PAIR_REJECT,
    GFSM_ACT_PASSKEY_CONFIRM,
    GFSM_ACT_PASSKEY_FAILED,
    GFSM_ACT_ENC_DONE,
    GFSM_ACT_ENC_DONE_BOND,
    GFSM_ACT_AUTH_FAIL_DISCONNECT,
    GFSM_ACT_ATT_INSUFFICIENT_AUTH,
    GFSM_ACT_CCCD_WRITE,
    GFSM_ACT_TIMEOUT_DISCONNECT,
    GFSM_ACT_APP_DISCONNECT,
    GFSM_ACT_LINK_LOST,
    GFSM_ACT_LINK_RESET,
    GFSM_ACT_COUNT
} gfsm_action_t;

typedef struct {
    cm_state_t from;
    cm_event_type_t event;
    gfsm_guard_t guard;
    cm_state_t to;
    gfsm_action_t action;
} gfsm_transition_t;

typedef void (*gfsm_action_fn)(cm_ctx_t *ctx, const cm_event_t *ev);
typedef void (*gfsm_observer_fn)(const gfsm_transition_t *t, const cm_ctx_t *ctx, const cm_event_t *ev, void *user);

const gfsm_transition_t *gfsm_table(size_t *count);
bool gfsm_guard_holds(gfsm_guard_t g, const cm_ctx_t *ctx, const cm_event_t *ev);
const gfsm_transition_t *gfsm_find(const cm_ctx_t *ctx, const cm_event_t *ev);
const gfsm_transition_t *gfsm_dispatch(cm_ctx_t *ctx, const cm_event_t *ev);

void gfsm_set_action_hook(gfsm_action_t a, gfsm_action_fn fn);
gfsm_action_fn gfsm_default_action(gfsm_action_t a);
void gfsm_set_observer(gfsm_observer_fn fn, void *user);

const char *gfsm_state_name(cm_state_t s);
const char *gfsm_event_name(cm_event_type_t e);
const char *gfsm_guard_name(gfsm_guard_t g);
const char *gfsm_action_name(gfsm_action_t a);

#endif
