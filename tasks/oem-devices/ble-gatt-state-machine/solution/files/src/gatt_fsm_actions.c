/* Default actions of the connection state machine (docs/conn_fsm.md "Actions"). */
#include <string.h>

#include "bond_store.h"
#include "evt_log.h"
#include "gatt_fsm.h"
#include "hal_ble.h"

static void reset_link(cm_ctx_t *ctx)
{
    memset(ctx->peer, 0, sizeof ctx->peer);
    ctx->has_peer = false;
    ctx->mtu = CM_MTU_DEFAULT;
    ctx->pair_attempts = 0;
    ctx->notify_enabled = false;
}

static void disconnect_with(uint8_t reason)
{
    hal_disconnect(reason);
    hal_timer_arm(CM_DISCONNECT_TIMEOUT_MS);
}

static void act_adv_start(cm_ctx_t *ctx, const cm_event_t *ev) { (void)ctx; (void)ev; hal_adv_start(); }
static void act_adv_stop(cm_ctx_t *ctx, const cm_event_t *ev) { (void)ctx; (void)ev; hal_adv_stop(); }

static void act_connect_new(cm_ctx_t *ctx, const cm_event_t *ev)
{
    memcpy(ctx->peer, ev->peer, 6);
    ctx->has_peer = true;
    hal_timer_arm(CM_SECURITY_TIMEOUT_MS);
    evt_log("CM new peer %02x", ev->peer[5]);
}

static void act_connect_bonded(cm_ctx_t *ctx, const cm_event_t *ev)
{
    memcpy(ctx->peer, ev->peer, 6);
    ctx->has_peer = true;
    hal_timer_arm(CM_SECURITY_TIMEOUT_MS);
    hal_enc_request(ev->peer);
    evt_log("CM bonded peer %02x", ev->peer[5]);
}

static void act_mtu_reply(cm_ctx_t *ctx, const cm_event_t *ev)
{
    uint16_t mtu = ev->mtu;
    if (mtu < CM_MTU_DEFAULT) {
        mtu = CM_MTU_DEFAULT;
    }
    if (mtu > CM_MTU_MAX) {
        mtu = CM_MTU_MAX;
    }
    ctx->mtu = mtu;
    hal_mtu_reply(mtu);
}

static void act_pair_start(cm_ctx_t *ctx, const cm_event_t *ev)
{
    (void)ev;
    ctx->pair_attempts++;
    hal_pairing_start();
}

static void act_pair_reject(cm_ctx_t *ctx, const cm_event_t *ev)
{
    (void)ctx; (void)ev;
    evt_log("CM pairing attempts exhausted");
    hal_pairing_reject();
    disconnect_with(CM_HCI_AUTH_FAILURE);
}

static void act_passkey_confirm(cm_ctx_t *ctx, const cm_event_t *ev) { (void)ctx; (void)ev; hal_pairing_confirm(); }

static void act_passkey_failed(cm_ctx_t *ctx, const cm_event_t *ev)
{
    (void)ev;
    evt_log("CM passkey mismatch (attempt %u)", ctx->pair_attempts);
    hal_pairing_failed();
}

static void act_enc_done(cm_ctx_t *ctx, const cm_event_t *ev) { (void)ctx; (void)ev; hal_timer_cancel(); }

static void act_enc_done_bond(cm_ctx_t *ctx, const cm_event_t *ev)
{
    (void)ev;
    hal_timer_cancel();
    bond_store_add(ctx->peer);
    evt_log("CM bonded %02x", ctx->peer[5]);
}

static void act_auth_fail(cm_ctx_t *ctx, const cm_event_t *ev)
{
    (void)ctx;
    evt_log("CM encryption failed %u", ev->status);
    disconnect_with(CM_HCI_AUTH_FAILURE);
}

static void act_att_insufficient_auth(cm_ctx_t *ctx, const cm_event_t *ev)
{
    (void)ctx;
    hal_att_error(ev->handle, CM_ATT_ERR_INSUFFICIENT_AUTH);
}

static void act_cccd_write(cm_ctx_t *ctx, const cm_event_t *ev)
{
    ctx->notify_enabled = (ev->value & 0x0001u) != 0u;
    hal_att_write_rsp(ev->handle);
}

static void act_timeout_disconnect(cm_ctx_t *ctx, const cm_event_t *ev)
{
    (void)ctx; (void)ev;
    evt_log("CM security timeout");
    disconnect_with(CM_HCI_CONN_TIMEOUT);
}

static void act_app_disconnect(cm_ctx_t *ctx, const cm_event_t *ev)
{
    (void)ctx; (void)ev;
    disconnect_with(CM_HCI_REMOTE_USER_TERMINATED);
}

static void act_link_lost(cm_ctx_t *ctx, const cm_event_t *ev)
{
    evt_log("CM link lost 0x%02x", ev->reason);
    hal_timer_cancel();
    reset_link(ctx);
    hal_adv_start();
}

static void act_link_reset(cm_ctx_t *ctx, const cm_event_t *ev)
{
    (void)ev;
    evt_log("CM disconnect timeout, resetting link");
    hal_link_reset();
    reset_link(ctx);
    hal_adv_start();
}

static const gfsm_action_fn defaults[GFSM_ACT_COUNT] = {
    [GFSM_ACT_NONE] = NULL,
    [GFSM_ACT_ADV_START] = act_adv_start,
    [GFSM_ACT_ADV_STOP] = act_adv_stop,
    [GFSM_ACT_CONNECT_NEW] = act_connect_new,
    [GFSM_ACT_CONNECT_BONDED] = act_connect_bonded,
    [GFSM_ACT_MTU_REPLY] = act_mtu_reply,
    [GFSM_ACT_PAIR_START] = act_pair_start,
    [GFSM_ACT_PAIR_REJECT] = act_pair_reject,
    [GFSM_ACT_PASSKEY_CONFIRM] = act_passkey_confirm,
    [GFSM_ACT_PASSKEY_FAILED] = act_passkey_failed,
    [GFSM_ACT_ENC_DONE] = act_enc_done,
    [GFSM_ACT_ENC_DONE_BOND] = act_enc_done_bond,
    [GFSM_ACT_AUTH_FAIL_DISCONNECT] = act_auth_fail,
    [GFSM_ACT_ATT_INSUFFICIENT_AUTH] = act_att_insufficient_auth,
    [GFSM_ACT_CCCD_WRITE] = act_cccd_write,
    [GFSM_ACT_TIMEOUT_DISCONNECT] = act_timeout_disconnect,
    [GFSM_ACT_APP_DISCONNECT] = act_app_disconnect,
    [GFSM_ACT_LINK_LOST] = act_link_lost,
    [GFSM_ACT_LINK_RESET] = act_link_reset,
};

gfsm_action_fn gfsm_default_action(gfsm_action_t a)
{
    return (unsigned)a < GFSM_ACT_COUNT ? defaults[a] : NULL;
}

/* exposed for conn_mgr.c */
void gfsm_reset_link(cm_ctx_t *ctx);
void gfsm_reset_link(cm_ctx_t *ctx)
{
    reset_link(ctx);
}
