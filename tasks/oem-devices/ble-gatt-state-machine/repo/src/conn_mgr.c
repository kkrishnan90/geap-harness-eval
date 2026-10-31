/* Connection manager for the DKM-2 BLE peripheral.
 *
 * History: started as the reference-design callback handler and grew per feature
 * request (bonding, passkey, CCCD gating, supervision timer). See docs/conn_fsm.md for the
 * intended state chart. */

#include "conn_mgr.h"

#include <string.h>

#include "bond_store.h"
#include "evt_log.h"
#include "hal_ble.h"

static const char *const event_names[CM_EV_COUNT] = {
    "ADV_START", "ADV_STOP", "CONNECTED", "DISCONNECTED", "MTU_REQ", "PAIR_REQ",
    "PASSKEY_RESULT", "ENC_CHANGED", "CCCD_WRITE", "TIMEOUT", "APP_DISCONNECT",
};

const char *cm_state_str(cm_state_t s)
{
    switch (s) {
    case CM_ST_IDLE:
        return "IDLE";
    case CM_ST_ADVERTISING:
        return "ADVERTISING";
    case CM_ST_CONNECTED:
        return "CONNECTED";
    case CM_ST_PAIRING:
        return "PAIRING";
    case CM_ST_ENCRYPTED:
        return "ENCRYPTED";
    case CM_ST_READY:
        return "READY";
    case CM_ST_DISCONNECTING:
        return "DISCONNECTING";
    default:
        return "?";
    }
}

static void reset_link(cm_ctx_t *ctx)
{
    memset(ctx->peer, 0, sizeof ctx->peer);
    ctx->has_peer = false;
    ctx->mtu = CM_MTU_DEFAULT;
    ctx->pair_attempts = 0;
    ctx->notify_enabled = false;
}

void cm_init(cm_ctx_t *ctx)
{
    ctx->state = CM_ST_IDLE;
    reset_link(ctx);
}

cm_state_t cm_state(const cm_ctx_t *ctx)
{
    return ctx->state;
}

static void go(cm_ctx_t *ctx, cm_state_t next, const cm_event_t *ev)
{
    if (next != ctx->state) {
        evt_log("CM %s -> %s (%s)", cm_state_str(ctx->state), cm_state_str(next), event_names[ev->type]);
    }
    ctx->state = next;
}

void cm_handle_event(cm_ctx_t *ctx, const cm_event_t *ev)
{
    if (ev == NULL || ev->type >= CM_EV_COUNT) {
        return;
    }

    switch (ctx->state) {
    case CM_ST_IDLE:
        if (ev->type == CM_EV_ADV_START) {
            hal_adv_start();
            go(ctx, CM_ST_ADVERTISING, ev);
        }
        break;

    case CM_ST_ADVERTISING:
        switch (ev->type) {
        case CM_EV_ADV_STOP:
            hal_adv_stop();
            go(ctx, CM_ST_IDLE, ev);
            break;
        case CM_EV_CONNECTED:
            memcpy(ctx->peer, ev->peer, 6);
            ctx->has_peer = true;
            if (bond_store_contains(ev->peer)) {
                /* known phone: re-encrypt with the stored LTK, no pairing */
                hal_timer_arm(CM_SECURITY_TIMEOUT_MS);
                hal_enc_request(ev->peer);
                evt_log("CM bonded peer %02x", ev->peer[5]);
            } else {
                hal_timer_arm(CM_SECURITY_TIMEOUT_MS);
                evt_log("CM new peer %02x", ev->peer[5]);
            }
            go(ctx, CM_ST_CONNECTED, ev);
            break;
        default:
            break;
        }
        break;

    case CM_ST_CONNECTED:
        switch (ev->type) {
        case CM_EV_MTU_REQ: {
            uint16_t mtu = ev->mtu;
            if (mtu < CM_MTU_DEFAULT) {
                mtu = CM_MTU_DEFAULT;
            }
            if (mtu > CM_MTU_MAX) {
                mtu = CM_MTU_MAX;
            }
            ctx->mtu = mtu;
            hal_mtu_reply(mtu);
            break;
        }
        case CM_EV_PAIR_REQ:
            if (ctx->pair_attempts < CM_MAX_PAIR_ATTEMPTS) {
                ctx->pair_attempts++;
                hal_pairing_start();
                go(ctx, CM_ST_PAIRING, ev);
            } else {
                evt_log("CM pairing attempts exhausted");
                hal_pairing_reject();
                hal_disconnect(CM_HCI_AUTH_FAILURE);
                hal_timer_arm(CM_DISCONNECT_TIMEOUT_MS);
                go(ctx, CM_ST_DISCONNECTING, ev);
            }
            break;
        case CM_EV_ENC_CHANGED:
            if (ev->status == 0) {
                hal_timer_cancel();
                go(ctx, CM_ST_ENCRYPTED, ev);
            } else {
                evt_log("CM encryption failed %u", ev->status);
                hal_disconnect(CM_HCI_AUTH_FAILURE);
                hal_timer_arm(CM_DISCONNECT_TIMEOUT_MS);
                go(ctx, CM_ST_DISCONNECTING, ev);
            }
            break;
        case CM_EV_CCCD_WRITE:
            /* key service requires an encrypted link */
            hal_att_error(ev->handle, CM_ATT_ERR_INSUFFICIENT_AUTH);
            break;
        case CM_EV_TIMEOUT:
            evt_log("CM security timeout");
            hal_disconnect(CM_HCI_CONN_TIMEOUT);
            hal_timer_arm(CM_DISCONNECT_TIMEOUT_MS);
            go(ctx, CM_ST_DISCONNECTING, ev);
            break;
        case CM_EV_APP_DISCONNECT:
            hal_disconnect(CM_HCI_REMOTE_USER_TERMINATED);
            hal_timer_arm(CM_DISCONNECT_TIMEOUT_MS);
            go(ctx, CM_ST_DISCONNECTING, ev);
            break;
        case CM_EV_DISCONNECTED:
            evt_log("CM link lost 0x%02x", ev->reason);
            hal_timer_cancel();
            reset_link(ctx);
            hal_adv_start();
            go(ctx, CM_ST_ADVERTISING, ev);
            break;
        default:
            break;
        }
        break;

    case CM_ST_PAIRING:
        switch (ev->type) {
        case CM_EV_MTU_REQ: {
            uint16_t mtu = ev->mtu;
            if (mtu < CM_MTU_DEFAULT) {
                mtu = CM_MTU_DEFAULT;
            }
            if (mtu > CM_MTU_MAX) {
                mtu = CM_MTU_MAX;
            }
            ctx->mtu = mtu;
            hal_mtu_reply(mtu);
            break;
        }
        case CM_EV_PASSKEY_RESULT:
            if (ev->status == 0) {
                hal_pairing_confirm();
            } else {
                evt_log("CM passkey mismatch (attempt %u)", ctx->pair_attempts);
                hal_pairing_failed();
                go(ctx, CM_ST_CONNECTED, ev);
            }
            break;
        case CM_EV_ENC_CHANGED:
            if (ev->status == 0) {
                hal_timer_cancel();
                bond_store_add(ctx->peer);
                evt_log("CM bonded %02x", ctx->peer[5]);
                go(ctx, CM_ST_ENCRYPTED, ev);
            } else {
                evt_log("CM encryption failed %u", ev->status);
                hal_disconnect(CM_HCI_AUTH_FAILURE);
                hal_timer_arm(CM_DISCONNECT_TIMEOUT_MS);
                go(ctx, CM_ST_DISCONNECTING, ev);
            }
            break;
        case CM_EV_CCCD_WRITE:
            hal_att_error(ev->handle, CM_ATT_ERR_INSUFFICIENT_AUTH);
            break;
        case CM_EV_TIMEOUT:
            /* phone did not finish the passkey dialog: let it try again */
            evt_log("CM pairing timeout");
            hal_pairing_failed();
            go(ctx, CM_ST_CONNECTED, ev);
            break;
        case CM_EV_APP_DISCONNECT:
            hal_disconnect(CM_HCI_REMOTE_USER_TERMINATED);
            hal_timer_arm(CM_DISCONNECT_TIMEOUT_MS);
            go(ctx, CM_ST_DISCONNECTING, ev);
            break;
        case CM_EV_DISCONNECTED:
            evt_log("CM link lost 0x%02x", ev->reason);
            hal_timer_cancel();
            reset_link(ctx);
            hal_adv_start();
            go(ctx, CM_ST_ADVERTISING, ev);
            break;
        default:
            break;
        }
        break;

    case CM_ST_ENCRYPTED:
        switch (ev->type) {
        case CM_EV_MTU_REQ: {
            uint16_t mtu = ev->mtu;
            if (mtu < CM_MTU_DEFAULT) {
                mtu = CM_MTU_DEFAULT;
            }
            if (mtu > CM_MTU_MAX) {
                mtu = CM_MTU_MAX;
            }
            ctx->mtu = mtu;
            hal_mtu_reply(mtu);
            break;
        }
        case CM_EV_CCCD_WRITE:
            ctx->notify_enabled = (ev->value & 0x0001u) != 0u;
            hal_att_write_rsp(ev->handle);
            if (ctx->notify_enabled) {
                go(ctx, CM_ST_READY, ev);
            }
            break;
        case CM_EV_APP_DISCONNECT:
            hal_disconnect(CM_HCI_REMOTE_USER_TERMINATED);
            hal_timer_arm(CM_DISCONNECT_TIMEOUT_MS);
            go(ctx, CM_ST_DISCONNECTING, ev);
            break;
        case CM_EV_DISCONNECTED:
            evt_log("CM link lost 0x%02x", ev->reason);
            hal_timer_cancel();
            reset_link(ctx);
            hal_adv_start();
            go(ctx, CM_ST_ADVERTISING, ev);
            break;
        default:
            break;
        }
        break;

    case CM_ST_READY:
        switch (ev->type) {
        case CM_EV_MTU_REQ: {
            uint16_t mtu = ev->mtu;
            if (mtu < CM_MTU_DEFAULT) {
                mtu = CM_MTU_DEFAULT;
            }
            if (mtu > CM_MTU_MAX) {
                mtu = CM_MTU_MAX;
            }
            ctx->mtu = mtu;
            hal_mtu_reply(mtu);
            break;
        }
        case CM_EV_CCCD_WRITE:
            ctx->notify_enabled = (ev->value & 0x0001u) != 0u;
            hal_att_write_rsp(ev->handle);
            if (!ctx->notify_enabled) {
                go(ctx, CM_ST_ENCRYPTED, ev);
            }
            break;
        case CM_EV_APP_DISCONNECT:
            hal_disconnect(CM_HCI_REMOTE_USER_TERMINATED);
            hal_timer_arm(CM_DISCONNECT_TIMEOUT_MS);
            go(ctx, CM_ST_DISCONNECTING, ev);
            break;
        case CM_EV_DISCONNECTED:
            evt_log("CM link lost 0x%02x", ev->reason);
            hal_timer_cancel();
            reset_link(ctx);
            hal_adv_start();
            go(ctx, CM_ST_ADVERTISING, ev);
            break;
        default:
            break;
        }
        break;

    case CM_ST_DISCONNECTING:
        switch (ev->type) {
        case CM_EV_DISCONNECTED:
            evt_log("CM disconnect complete 0x%02x", ev->reason);
            hal_timer_cancel();
            reset_link(ctx);
            hal_adv_start();
            go(ctx, CM_ST_ADVERTISING, ev);
            break;
        case CM_EV_TIMEOUT:
            /* controller never confirmed: force it */
            evt_log("CM disconnect timeout, resetting link");
            hal_link_reset();
            reset_link(ctx);
            hal_adv_start();
            go(ctx, CM_ST_ADVERTISING, ev);
            break;
        default:
            break;
        }
        break;

    default:
        break;
    }
}
