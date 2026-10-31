/* Transition table, guards and dispatch of the connection state machine. */
#include "gatt_fsm.h"

#include "bond_store.h"
#include "evt_log.h"

#define ROW(f, e, g, t, a) {CM_ST_##f, CM_EV_##e, GFSM_GUARD_##g, CM_ST_##t, GFSM_ACT_##a}

/* Order matters: for the same (from, event) guarded rows come first. */
static const gfsm_transition_t table[] = {
    ROW(IDLE, ADV_START, NONE, ADVERTISING, ADV_START),
    ROW(ADVERTISING, ADV_STOP, NONE, IDLE, ADV_STOP),
    ROW(ADVERTISING, CONNECTED, PEER_BONDED, CONNECTED, CONNECT_BONDED),
    ROW(ADVERTISING, CONNECTED, NONE, CONNECTED, CONNECT_NEW),
    ROW(CONNECTED, MTU_REQ, NONE, CONNECTED, MTU_REPLY),
    ROW(CONNECTED, PAIR_REQ, PAIR_ATTEMPTS_LEFT, PAIRING, PAIR_START),
    ROW(CONNECTED, PAIR_REQ, NONE, DISCONNECTING, PAIR_REJECT),
    ROW(CONNECTED, ENC_CHANGED, STATUS_OK, ENCRYPTED, ENC_DONE),
    ROW(CONNECTED, ENC_CHANGED, NONE, DISCONNECTING, AUTH_FAIL_DISCONNECT),
    ROW(CONNECTED, CCCD_WRITE, NONE, CONNECTED, ATT_INSUFFICIENT_AUTH),
    ROW(CONNECTED, TIMEOUT, NONE, DISCONNECTING, TIMEOUT_DISCONNECT),
    ROW(CONNECTED, APP_DISCONNECT, NONE, DISCONNECTING, APP_DISCONNECT),
    ROW(CONNECTED, DISCONNECTED, NONE, ADVERTISING, LINK_LOST),
    ROW(PAIRING, MTU_REQ, NONE, PAIRING, MTU_REPLY),
    ROW(PAIRING, PASSKEY_RESULT, STATUS_OK, PAIRING, PASSKEY_CONFIRM),
    ROW(PAIRING, PASSKEY_RESULT, NONE, CONNECTED, PASSKEY_FAILED),
    ROW(PAIRING, ENC_CHANGED, STATUS_OK, ENCRYPTED, ENC_DONE_BOND),
    ROW(PAIRING, ENC_CHANGED, NONE, DISCONNECTING, AUTH_FAIL_DISCONNECT),
    ROW(PAIRING, CCCD_WRITE, NONE, PAIRING, ATT_INSUFFICIENT_AUTH),
    ROW(PAIRING, TIMEOUT, NONE, DISCONNECTING, TIMEOUT_DISCONNECT),
    ROW(PAIRING, APP_DISCONNECT, NONE, DISCONNECTING, APP_DISCONNECT),
    ROW(PAIRING, DISCONNECTED, NONE, ADVERTISING, LINK_LOST),
    ROW(ENCRYPTED, MTU_REQ, NONE, ENCRYPTED, MTU_REPLY),
    ROW(ENCRYPTED, CCCD_WRITE, CCCD_ENABLE, READY, CCCD_WRITE),
    ROW(ENCRYPTED, CCCD_WRITE, NONE, ENCRYPTED, CCCD_WRITE),
    ROW(ENCRYPTED, APP_DISCONNECT, NONE, DISCONNECTING, APP_DISCONNECT),
    ROW(ENCRYPTED, DISCONNECTED, NONE, ADVERTISING, LINK_LOST),
    ROW(READY, MTU_REQ, NONE, READY, MTU_REPLY),
    ROW(READY, CCCD_WRITE, CCCD_ENABLE, READY, CCCD_WRITE),
    ROW(READY, CCCD_WRITE, NONE, ENCRYPTED, CCCD_WRITE),
    ROW(READY, APP_DISCONNECT, NONE, DISCONNECTING, APP_DISCONNECT),
    ROW(READY, DISCONNECTED, NONE, ADVERTISING, LINK_LOST),
    ROW(DISCONNECTING, DISCONNECTED, NONE, ADVERTISING, LINK_LOST),
    ROW(DISCONNECTING, TIMEOUT, NONE, ADVERTISING, LINK_RESET),
};

#define TABLE_LEN (sizeof table / sizeof table[0])

static const char *const state_names[CM_ST_COUNT] = {
    "IDLE", "ADVERTISING", "CONNECTED", "PAIRING", "ENCRYPTED", "READY", "DISCONNECTING",
};
static const char *const event_names[CM_EV_COUNT] = {
    "ADV_START", "ADV_STOP", "CONNECTED", "DISCONNECTED", "MTU_REQ", "PAIR_REQ",
    "PASSKEY_RESULT", "ENC_CHANGED", "CCCD_WRITE", "TIMEOUT", "APP_DISCONNECT",
};
static const char *const guard_names[GFSM_GUARD_COUNT] = {
    "NONE", "PEER_BONDED", "PAIR_ATTEMPTS_LEFT", "STATUS_OK", "CCCD_ENABLE",
};
static const char *const action_names[GFSM_ACT_COUNT] = {
    "NONE", "ADV_START", "ADV_STOP", "CONNECT_NEW", "CONNECT_BONDED", "MTU_REPLY", "PAIR_START",
    "PAIR_REJECT", "PASSKEY_CONFIRM", "PASSKEY_FAILED", "ENC_DONE", "ENC_DONE_BOND",
    "AUTH_FAIL_DISCONNECT", "ATT_INSUFFICIENT_AUTH", "CCCD_WRITE", "TIMEOUT_DISCONNECT",
    "APP_DISCONNECT", "LINK_LOST", "LINK_RESET",
};

static gfsm_action_fn hooks[GFSM_ACT_COUNT];
static gfsm_observer_fn observer;
static void *observer_user;

const gfsm_transition_t *gfsm_table(size_t *count)
{
    if (count != NULL) {
        *count = TABLE_LEN;
    }
    return table;
}

bool gfsm_guard_holds(gfsm_guard_t g, const cm_ctx_t *ctx, const cm_event_t *ev)
{
    switch (g) {
    case GFSM_GUARD_NONE:
        return true;
    case GFSM_GUARD_PEER_BONDED:
        return bond_store_contains(ev->peer);
    case GFSM_GUARD_PAIR_ATTEMPTS_LEFT:
        return ctx->pair_attempts < CM_MAX_PAIR_ATTEMPTS;
    case GFSM_GUARD_STATUS_OK:
        return ev->status == 0u;
    case GFSM_GUARD_CCCD_ENABLE:
        return (ev->value & 0x0001u) != 0u;
    default:
        return false;
    }
}

const gfsm_transition_t *gfsm_find(const cm_ctx_t *ctx, const cm_event_t *ev)
{
    if (ctx == NULL || ev == NULL || ev->type >= CM_EV_COUNT) {
        return NULL;
    }
    for (size_t i = 0; i < TABLE_LEN; i++) {
        const gfsm_transition_t *t = &table[i];
        if (t->from == ctx->state && t->event == ev->type && gfsm_guard_holds(t->guard, ctx, ev)) {
            return t;
        }
    }
    return NULL;
}

const gfsm_transition_t *gfsm_dispatch(cm_ctx_t *ctx, const cm_event_t *ev)
{
    const gfsm_transition_t *t = gfsm_find(ctx, ev);
    if (t == NULL) {
        return NULL;
    }
    gfsm_action_fn fn = hooks[t->action] != NULL ? hooks[t->action] : gfsm_default_action(t->action);
    if (fn != NULL) {
        fn(ctx, ev);
    }
    if (t->to != ctx->state) {
        evt_log("CM %s -> %s (%s)", state_names[ctx->state], state_names[t->to], event_names[ev->type]);
    }
    ctx->state = t->to;
    if (observer != NULL) {
        observer(t, ctx, ev, observer_user);
    }
    return t;
}

void gfsm_set_action_hook(gfsm_action_t a, gfsm_action_fn fn)
{
    if ((unsigned)a < GFSM_ACT_COUNT) {
        hooks[a] = fn;
    }
}

void gfsm_set_observer(gfsm_observer_fn fn, void *user)
{
    observer = fn;
    observer_user = user;
}

const char *gfsm_state_name(cm_state_t s)
{
    return (unsigned)s < CM_ST_COUNT ? state_names[s] : "?";
}

const char *gfsm_event_name(cm_event_type_t e)
{
    return (unsigned)e < CM_EV_COUNT ? event_names[e] : "?";
}

const char *gfsm_guard_name(gfsm_guard_t g)
{
    return (unsigned)g < GFSM_GUARD_COUNT ? guard_names[g] : "?";
}

const char *gfsm_action_name(gfsm_action_t a)
{
    return (unsigned)a < GFSM_ACT_COUNT ? action_names[a] : "?";
}
