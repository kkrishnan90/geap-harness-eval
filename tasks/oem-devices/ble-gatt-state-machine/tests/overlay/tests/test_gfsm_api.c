/* Table-driven FSM API (include/gatt_fsm.h). */
#include <stdio.h>
#include <string.h>

#include "gatt_fsm.h"
#include "unit.h"
#include "cm_helpers.h"

typedef struct { int from, event, guard, to, action; } spec_row_t;

#define R(f, e, g, t, a) {CM_ST_##f, CM_EV_##e, GFSM_GUARD_##g, CM_ST_##t, GFSM_ACT_##a}
static const spec_row_t SPEC[] = {
    R(IDLE, ADV_START, NONE, ADVERTISING, ADV_START),
    R(ADVERTISING, ADV_STOP, NONE, IDLE, ADV_STOP),
    R(ADVERTISING, CONNECTED, PEER_BONDED, CONNECTED, CONNECT_BONDED),
    R(ADVERTISING, CONNECTED, NONE, CONNECTED, CONNECT_NEW),
    R(CONNECTED, MTU_REQ, NONE, CONNECTED, MTU_REPLY),
    R(CONNECTED, PAIR_REQ, PAIR_ATTEMPTS_LEFT, PAIRING, PAIR_START),
    R(CONNECTED, PAIR_REQ, NONE, DISCONNECTING, PAIR_REJECT),
    R(CONNECTED, ENC_CHANGED, STATUS_OK, ENCRYPTED, ENC_DONE),
    R(CONNECTED, ENC_CHANGED, NONE, DISCONNECTING, AUTH_FAIL_DISCONNECT),
    R(CONNECTED, CCCD_WRITE, NONE, CONNECTED, ATT_INSUFFICIENT_AUTH),
    R(CONNECTED, TIMEOUT, NONE, DISCONNECTING, TIMEOUT_DISCONNECT),
    R(CONNECTED, APP_DISCONNECT, NONE, DISCONNECTING, APP_DISCONNECT),
    R(CONNECTED, DISCONNECTED, NONE, ADVERTISING, LINK_LOST),
    R(PAIRING, MTU_REQ, NONE, PAIRING, MTU_REPLY),
    R(PAIRING, PASSKEY_RESULT, STATUS_OK, PAIRING, PASSKEY_CONFIRM),
    R(PAIRING, PASSKEY_RESULT, NONE, CONNECTED, PASSKEY_FAILED),
    R(PAIRING, ENC_CHANGED, STATUS_OK, ENCRYPTED, ENC_DONE_BOND),
    R(PAIRING, ENC_CHANGED, NONE, DISCONNECTING, AUTH_FAIL_DISCONNECT),
    R(PAIRING, CCCD_WRITE, NONE, PAIRING, ATT_INSUFFICIENT_AUTH),
    R(PAIRING, TIMEOUT, NONE, DISCONNECTING, TIMEOUT_DISCONNECT),
    R(PAIRING, APP_DISCONNECT, NONE, DISCONNECTING, APP_DISCONNECT),
    R(PAIRING, DISCONNECTED, NONE, ADVERTISING, LINK_LOST),
    R(ENCRYPTED, MTU_REQ, NONE, ENCRYPTED, MTU_REPLY),
    R(ENCRYPTED, CCCD_WRITE, CCCD_ENABLE, READY, CCCD_WRITE),
    R(ENCRYPTED, CCCD_WRITE, NONE, ENCRYPTED, CCCD_WRITE),
    R(ENCRYPTED, APP_DISCONNECT, NONE, DISCONNECTING, APP_DISCONNECT),
    R(ENCRYPTED, DISCONNECTED, NONE, ADVERTISING, LINK_LOST),
    R(READY, MTU_REQ, NONE, READY, MTU_REPLY),
    R(READY, CCCD_WRITE, CCCD_ENABLE, READY, CCCD_WRITE),
    R(READY, CCCD_WRITE, NONE, ENCRYPTED, CCCD_WRITE),
    R(READY, APP_DISCONNECT, NONE, DISCONNECTING, APP_DISCONNECT),
    R(READY, DISCONNECTED, NONE, ADVERTISING, LINK_LOST),
    R(DISCONNECTING, DISCONNECTED, NONE, ADVERTISING, LINK_LOST),
    R(DISCONNECTING, TIMEOUT, NONE, ADVERTISING, LINK_RESET),
};
#define N_SPEC (sizeof SPEC / sizeof SPEC[0])

static int row_index(const gfsm_transition_t *tab, size_t n, const spec_row_t *s)
{
    for (size_t i = 0; i < n; i++) {
        if ((int)tab[i].from == s->from && (int)tab[i].event == s->event && (int)tab[i].guard == s->guard &&
            (int)tab[i].to == s->to && (int)tab[i].action == s->action) {
            return (int)i;
        }
    }
    return -1;
}

TEST(table_matches_design)
{
    size_t n = 0;
    const gfsm_transition_t *tab = gfsm_table(&n);
    CHECK(tab != NULL);
    CHECK_EQ_INT(N_SPEC, n);
    int idx[N_SPEC];
    for (size_t i = 0; i < N_SPEC; i++) {
        idx[i] = tab ? row_index(tab, n, &SPEC[i]) : -1;
        if (idx[i] < 0) {
            printf("  missing row %zu: %s/%s\n", i + 1, gfsm_state_name(SPEC[i].from), gfsm_event_name(SPEC[i].event));
            unit_failed_ = 1;
        }
    }
    /* rows for the same (from, event) keep their relative order (guarded first) */
    for (size_t i = 0; i < N_SPEC; i++) {
        for (size_t j = i + 1; j < N_SPEC; j++) {
            if (SPEC[i].from == SPEC[j].from && SPEC[i].event == SPEC[j].event && idx[i] >= 0 && idx[j] >= 0) {
                CHECK(idx[i] < idx[j]);
            }
        }
    }
}

TEST(names)
{
    const char *states[] = {"IDLE", "ADVERTISING", "CONNECTED", "PAIRING", "ENCRYPTED", "READY", "DISCONNECTING"};
    const char *events[] = {"ADV_START", "ADV_STOP", "CONNECTED", "DISCONNECTED", "MTU_REQ", "PAIR_REQ",
                            "PASSKEY_RESULT", "ENC_CHANGED", "CCCD_WRITE", "TIMEOUT", "APP_DISCONNECT"};
    const char *guards[] = {"NONE", "PEER_BONDED", "PAIR_ATTEMPTS_LEFT", "STATUS_OK", "CCCD_ENABLE"};
    const char *actions[] = {"NONE", "ADV_START", "ADV_STOP", "CONNECT_NEW", "CONNECT_BONDED", "MTU_REPLY",
                             "PAIR_START", "PAIR_REJECT", "PASSKEY_CONFIRM", "PASSKEY_FAILED", "ENC_DONE",
                             "ENC_DONE_BOND", "AUTH_FAIL_DISCONNECT", "ATT_INSUFFICIENT_AUTH", "CCCD_WRITE",
                             "TIMEOUT_DISCONNECT", "APP_DISCONNECT", "LINK_LOST", "LINK_RESET"};
    CHECK_EQ_INT(7, CM_ST_COUNT);
    CHECK_EQ_INT(19, GFSM_ACT_COUNT);
    CHECK_EQ_INT(5, GFSM_GUARD_COUNT);
    for (int i = 0; i < CM_ST_COUNT; i++) {
        CHECK(strcmp(states[i], gfsm_state_name((cm_state_t)i)) == 0);
        CHECK(strcmp(states[i], cm_state_str((cm_state_t)i)) == 0);
    }
    for (int i = 0; i < CM_EV_COUNT; i++) CHECK(strcmp(events[i], gfsm_event_name((cm_event_type_t)i)) == 0);
    for (int i = 0; i < GFSM_GUARD_COUNT; i++) CHECK(strcmp(guards[i], gfsm_guard_name((gfsm_guard_t)i)) == 0);
    for (int i = 0; i < GFSM_ACT_COUNT; i++) CHECK(strcmp(actions[i], gfsm_action_name((gfsm_action_t)i)) == 0);
    CHECK(strcmp("?", gfsm_state_name(CM_ST_COUNT)) == 0);
    CHECK(strcmp("?", gfsm_event_name(CM_EV_COUNT)) == 0);
    CHECK(strcmp("?", gfsm_action_name(GFSM_ACT_COUNT)) == 0);
}

TEST(guards)
{
    cm_ctx_t c;
    fresh(&c);
    cm_event_t e = ev_of(CM_EV_CONNECTED);
    memcpy(e.peer, PHONE_B, 6);
    CHECK(gfsm_guard_holds(GFSM_GUARD_NONE, &c, &e));
    CHECK(!gfsm_guard_holds(GFSM_GUARD_PEER_BONDED, &c, &e));
    bond_store_add(PHONE_B);
    CHECK(gfsm_guard_holds(GFSM_GUARD_PEER_BONDED, &c, &e));
    c.pair_attempts = 2;
    CHECK(gfsm_guard_holds(GFSM_GUARD_PAIR_ATTEMPTS_LEFT, &c, &e));
    c.pair_attempts = 3;
    CHECK(!gfsm_guard_holds(GFSM_GUARD_PAIR_ATTEMPTS_LEFT, &c, &e));
    e.status = 0;
    CHECK(gfsm_guard_holds(GFSM_GUARD_STATUS_OK, &c, &e));
    e.status = 0x3D;
    CHECK(!gfsm_guard_holds(GFSM_GUARD_STATUS_OK, &c, &e));
    e.value = 0x0003;
    CHECK(gfsm_guard_holds(GFSM_GUARD_CCCD_ENABLE, &c, &e));
    e.value = 0x0002;
    CHECK(!gfsm_guard_holds(GFSM_GUARD_CCCD_ENABLE, &c, &e));
}

/* every (state, event, payload variant): gfsm_find agrees with what cm_handle_event does */
TEST(find_agrees_with_runtime)
{
    for (int s = 0; s < CM_ST_COUNT; s++) {
        for (int ev = 0; ev < CM_EV_COUNT; ev++) {
            for (int variant = 0; variant < 8; variant++) {
                cm_ctx_t c;
                fresh(&c);
                if (variant & 4) bond_store_add(PHONE_A);
                c.state = (cm_state_t)s;
                c.has_peer = s >= CM_ST_CONNECTED;
                if (c.has_peer) memcpy(c.peer, PHONE_A, 6);
                c.pair_attempts = (variant & 2) ? 3 : 1;
                cm_event_t e = ev_of((cm_event_type_t)ev);
                memcpy(e.peer, PHONE_A, 6);
                e.status = (variant & 1) ? 7 : 0;
                e.value = (variant & 1) ? 0 : 1;
                e.mtu = 100;
                e.handle = 0x2A;
                const gfsm_transition_t *t = gfsm_find(&c, &e);
                cm_ctx_t before = c;
                cm_handle_event(&c, &e);
                if (t == NULL) {
                    CHECK_EQ_INT(s, c.state);
                    CHECK_EQ_INT(0, strlen(hal_stub_calls()));
                    CHECK(before.has_peer == c.has_peer && before.mtu == c.mtu &&
                          before.pair_attempts == c.pair_attempts && before.notify_enabled == c.notify_enabled &&
                          memcmp(before.peer, c.peer, 6) == 0);
                } else {
                    CHECK_EQ_INT(s, t->from);
                    CHECK_EQ_INT(ev, t->event);
                    CHECK_EQ_INT(t->to, c.state);
                }
                if (unit_failed_) {
                    printf("  at state %s event %s variant %d\n", gfsm_state_name((cm_state_t)s),
                           gfsm_event_name((cm_event_type_t)ev), variant);
                    return;
                }
            }
        }
    }
}

static int hook_calls;
static cm_state_t hook_saw_state;
static void counting_hook(cm_ctx_t *ctx, const cm_event_t *ev)
{
    (void)ev;
    hook_calls++;
    hook_saw_state = ctx->state;
}

TEST(action_hook_override)
{
    cm_ctx_t c;
    fresh(&c);
    CHECK(gfsm_default_action(GFSM_ACT_NONE) == NULL);
    for (int a = 1; a < GFSM_ACT_COUNT; a++) CHECK(gfsm_default_action((gfsm_action_t)a) != NULL);
    hook_calls = 0;
    gfsm_set_action_hook(GFSM_ACT_ADV_START, counting_hook);
    send(&c, CM_EV_ADV_START);
    CHECK_EQ_INT(1, hook_calls);
    CHECK_EQ_INT(CM_ST_IDLE, hook_saw_state); /* action runs before the state change */
    CHECK_EQ_INT(CM_ST_ADVERTISING, cm_state(&c));
    CHECK_CALLS("");
    gfsm_set_action_hook(GFSM_ACT_ADV_START, NULL);
    send(&c, CM_EV_ADV_STOP);
    send(&c, CM_EV_ADV_START);
    CHECK_EQ_INT(1, hook_calls);
    CHECK_CALLS("adv_stop;adv_start");
}

static char obs_buf[512];
static void observer(const gfsm_transition_t *t, const cm_ctx_t *ctx, const cm_event_t *ev, void *user)
{
    size_t l = strlen(obs_buf);
    snprintf(obs_buf + l, sizeof obs_buf - l, "%s%s>%s:%s@%s", l ? " " : "", gfsm_state_name(t->from),
             gfsm_state_name(t->to), gfsm_action_name(t->action), gfsm_state_name(ctx->state));
    CHECK(ev != NULL);
    CHECK(user == (void *)obs_buf);
}

TEST(observer_sees_taken_transitions)
{
    cm_ctx_t c;
    fresh(&c);
    obs_buf[0] = '\0';
    gfsm_set_observer(observer, obs_buf);
    send(&c, CM_EV_TIMEOUT);          /* ignored: no callback */
    send(&c, CM_EV_ADV_START);
    send_connect(&c, PHONE_A);
    send_mtu(&c, 99);                 /* internal transition */
    gfsm_set_observer(NULL, NULL);
    send(&c, CM_EV_APP_DISCONNECT);
    CHECK(strcmp(obs_buf, "IDLE>ADVERTISING:ADV_START@ADVERTISING ADVERTISING>CONNECTED:CONNECT_NEW@CONNECTED "
                          "CONNECTED>CONNECTED:MTU_REPLY@CONNECTED") == 0);
    if (unit_failed_) printf("  observer log: %s\n", obs_buf);
}

TEST(dispatch_returns_table_row)
{
    cm_ctx_t c;
    fresh(&c);
    size_t n;
    const gfsm_transition_t *tab = gfsm_table(&n);
    cm_event_t e = ev_of(CM_EV_ADV_START);
    const gfsm_transition_t *t = gfsm_dispatch(&c, &e);
    CHECK(t != NULL && t >= tab && t < tab + n);
    CHECK(t != NULL && t->action == GFSM_ACT_ADV_START);
    CHECK(gfsm_dispatch(&c, &e) == NULL); /* ADV_START while advertising: ignored */
    e.type = CM_EV_COUNT;
    CHECK(gfsm_dispatch(&c, &e) == NULL);
    CHECK_EQ_INT(CM_ST_ADVERTISING, c.state);
}

/* design fix: a pairing that times out drops the link (was: back to CONNECTED) */
TEST(pairing_timeout_disconnects)
{
    cm_ctx_t c;
    fresh(&c);
    send(&c, CM_EV_ADV_START);
    send_connect(&c, PHONE_A);
    send(&c, CM_EV_PAIR_REQ);
    hal_stub_reset();
    send(&c, CM_EV_TIMEOUT);
    CHECK_EQ_INT(CM_ST_DISCONNECTING, cm_state(&c));
    CHECK_CALLS("disconnect:0x08;timer_arm:2000");
    send(&c, CM_EV_DISCONNECTED);
    CHECK_EQ_INT(CM_ST_ADVERTISING, cm_state(&c));
    CHECK_EQ_INT(0, c.pair_attempts);
}

int main(void)
{
    RUN("gfsm", table_matches_design);
    RUN("gfsm", names);
    RUN("gfsm", guards);
    RUN("gfsm", find_agrees_with_runtime);
    RUN("gfsm", action_hook_override);
    RUN("gfsm", observer_sees_taken_transitions);
    RUN("gfsm", dispatch_returns_table_row);
    RUN("gfsm", pairing_timeout_disconnects);
    UNIT_EXIT();
}
