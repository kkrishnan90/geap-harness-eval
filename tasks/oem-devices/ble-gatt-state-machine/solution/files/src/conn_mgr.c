/* Connection manager for the DKM-2 BLE peripheral: facade over the table-driven state
 * machine in gatt_fsm.c (transition table: docs/conn_fsm.md). */

#include "conn_mgr.h"

#include "gatt_fsm.h"

void gfsm_reset_link(cm_ctx_t *ctx);

const char *cm_state_str(cm_state_t s)
{
    return gfsm_state_name(s);
}

void cm_init(cm_ctx_t *ctx)
{
    ctx->state = CM_ST_IDLE;
    gfsm_reset_link(ctx);
}

cm_state_t cm_state(const cm_ctx_t *ctx)
{
    return ctx->state;
}

void cm_handle_event(cm_ctx_t *ctx, const cm_event_t *ev)
{
    (void)gfsm_dispatch(ctx, ev);
}
