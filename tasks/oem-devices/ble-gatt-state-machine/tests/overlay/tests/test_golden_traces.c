/* Golden traces recorded from the pre-refactor connection manager (release 4.2.0).
 * The refactor must reproduce them exactly: states after each event, HAL calls, context. */
#include <stdio.h>
#include <string.h>

#include "bond_store.h"
#include "conn_mgr.h"
#include "evt_log.h"
#include "hal_ble.h"
#include "unit.h"

/* golden trace definitions shared by generator and test */
typedef struct { int type; int status; int value; int mtu; int peer; int handle; } step_t;
#define S(t) {t, 0, 0, 0, 0, 0}
#define SS(t, st) {t, st, 0, 0, 0, 0}
#define CON(p) {CM_EV_CONNECTED, 0, 0, 0, p, 0}
#define MTU(m) {CM_EV_MTU_REQ, 0, 0, m, 0, 0}
#define CCCD(h, v) {CM_EV_CCCD_WRITE, 0, v, 0, 0, h}
#define END {-1, 0, 0, 0, 0, 0}
typedef struct { const char *name; int prebond_b; step_t steps[24]; } trace_t;

static const trace_t TRACES[] = {
    {"full_session_new_phone", 0, {S(CM_EV_ADV_START), CON(1), MTU(185), S(CM_EV_PAIR_REQ), SS(CM_EV_PASSKEY_RESULT, 0),
        SS(CM_EV_ENC_CHANGED, 0), CCCD(0x2A, 1), MTU(300), CCCD(0x2A, 0), CCCD(0x2A, 2), CCCD(0x2A, 3),
        S(CM_EV_APP_DISCONNECT), S(CM_EV_DISCONNECTED), END}},
    {"bonded_reconnect_and_link_loss", 1, {S(CM_EV_ADV_START), CON(2), CCCD(0x2A, 1), SS(CM_EV_ENC_CHANGED, 0),
        S(CM_EV_TIMEOUT), CCCD(0x2A, 1), S(CM_EV_PAIR_REQ), S(CM_EV_DISCONNECTED), S(CM_EV_ADV_STOP), END}},
    {"bonded_encryption_fails", 1, {S(CM_EV_ADV_START), CON(2), SS(CM_EV_ENC_CHANGED, 6), S(CM_EV_MTU_REQ),
        S(CM_EV_TIMEOUT), CON(1), S(CM_EV_DISCONNECTED), END}},
    {"passkey_retries_exhausted", 0, {S(CM_EV_ADV_START), CON(1), S(CM_EV_PAIR_REQ), SS(CM_EV_PASSKEY_RESULT, 1),
        S(CM_EV_PAIR_REQ), MTU(64), SS(CM_EV_PASSKEY_RESULT, 2), S(CM_EV_PAIR_REQ), SS(CM_EV_PASSKEY_RESULT, 1),
        S(CM_EV_PAIR_REQ), S(CM_EV_PAIR_REQ), S(CM_EV_DISCONNECTED), CON(1), S(CM_EV_PAIR_REQ), END}},
    {"pairing_encryption_failure", 0, {S(CM_EV_ADV_START), CON(1), S(CM_EV_PAIR_REQ), CCCD(0x30, 1),
        SS(CM_EV_PASSKEY_RESULT, 0), SS(CM_EV_ENC_CHANGED, 5), SS(CM_EV_ENC_CHANGED, 0), S(CM_EV_TIMEOUT),
        S(CM_EV_ADV_START), END}},
    {"ignored_events_in_idle_and_adv", 0, {S(CM_EV_ADV_STOP), S(CM_EV_TIMEOUT), CON(1), S(CM_EV_DISCONNECTED),
        S(CM_EV_ADV_START), S(CM_EV_TIMEOUT), S(CM_EV_PAIR_REQ), MTU(100), CCCD(0x2A, 1), S(CM_EV_APP_DISCONNECT),
        S(CM_EV_ADV_STOP), S(CM_EV_ADV_STOP), END}},
    {"app_disconnect_while_pairing", 0, {S(CM_EV_ADV_START), CON(1), S(CM_EV_PAIR_REQ), S(CM_EV_APP_DISCONNECT),
        SS(CM_EV_PASSKEY_RESULT, 0), S(CM_EV_TIMEOUT), CON(2), S(CM_EV_APP_DISCONNECT), S(CM_EV_DISCONNECTED), END}},
    {"ready_link_lost_resets_context", 0, {S(CM_EV_ADV_START), CON(1), S(CM_EV_PAIR_REQ), SS(CM_EV_PASSKEY_RESULT, 0),
        SS(CM_EV_ENC_CHANGED, 0), CCCD(0x2A, 1), S(CM_EV_TIMEOUT), S(CM_EV_DISCONNECTED), CON(1),
        SS(CM_EV_ENC_CHANGED, 0), CCCD(0x2A, 1), S(CM_EV_DISCONNECTED), END}},
};
#define N_TRACES (sizeof TRACES / sizeof TRACES[0])

static const uint8_t TPEER[3][6] = {{0}, {0x10, 0x20, 0x30, 0x40, 0x50, 0xA1}, {0x11, 0x21, 0x31, 0x41, 0x51, 0xB2}};

/* runs a trace; writes "STATE,STATE,..." into states and context summary into ctxs */
static void run_trace(const trace_t *t, char *states, size_t ns, char *ctxs, size_t nc)
{
    cm_ctx_t c;
    bond_store_clear();
    evt_log_clear();
    if (t->prebond_b) bond_store_add(TPEER[2]);
    cm_init(&c);
    hal_stub_reset();
    states[0] = '\0';
    ctxs[0] = '\0';
    for (int i = 0; t->steps[i].type >= 0; i++) {
        cm_event_t e;
        memset(&e, 0, sizeof e);
        e.type = (cm_event_type_t)t->steps[i].type;
        e.status = (uint8_t)t->steps[i].status;
        e.value = (uint16_t)t->steps[i].value;
        e.mtu = (uint16_t)t->steps[i].mtu;
        e.handle = (uint16_t)t->steps[i].handle;
        memcpy(e.peer, TPEER[t->steps[i].peer], 6);
        cm_handle_event(&c, &e);
        size_t l = strlen(states);
        snprintf(states + l, ns - l, "%s%s", l ? "," : "", cm_state_str(cm_state(&c)));
        l = strlen(ctxs);
        snprintf(ctxs + l, nc - l, "%s%d/%u/%u/%d/%d", l ? "," : "", c.has_peer ? c.peer[5] : 0, c.mtu,
                 c.pair_attempts, c.notify_enabled, bond_store_count());
    }
}

typedef struct { const char *name, *states, *calls, *ctx; } golden_t;

static const golden_t GOLDEN[] = {
    {"full_session_new_phone",
     "ADVERTISING,CONNECTED,CONNECTED,PAIRING,PAIRING,ENCRYPTED,READY,READY,ENCRYPTED,ENCRYPTED,READY,DISCONNECTING,ADVERTISING",
     "adv_start;timer_arm:30000;mtu_reply:185;pairing_start;pairing_confirm;timer_cancel;att_write_rsp:0x002a;mtu_reply:247;att_write_rsp:0x002a;att_write_rsp:0x002a;att_write_rsp:0x002a;disconnect:0x13;timer_arm:2000;timer_cancel;adv_start",
     "0/23/0/0/0,161/23/0/0/0,161/185/0/0/0,161/185/1/0/0,161/185/1/0/0,161/185/1/0/1,161/185/1/1/1,161/247/1/1/1,161/247/1/0/1,161/247/1/0/1,161/247/1/1/1,161/247/1/1/1,0/23/0/0/1"},
    {"bonded_reconnect_and_link_loss",
     "ADVERTISING,CONNECTED,CONNECTED,ENCRYPTED,ENCRYPTED,READY,READY,ADVERTISING,IDLE",
     "adv_start;timer_arm:30000;enc_request:b2;att_error:0x002a:05;timer_cancel;att_write_rsp:0x002a;timer_cancel;adv_start;adv_stop",
     "0/23/0/0/1,178/23/0/0/1,178/23/0/0/1,178/23/0/0/1,178/23/0/0/1,178/23/0/1/1,178/23/0/1/1,0/23/0/0/1,0/23/0/0/1"},
    {"bonded_encryption_fails",
     "ADVERTISING,CONNECTED,DISCONNECTING,DISCONNECTING,ADVERTISING,CONNECTED,ADVERTISING",
     "adv_start;timer_arm:30000;enc_request:b2;disconnect:0x05;timer_arm:2000;link_reset;adv_start;timer_arm:30000;timer_cancel;adv_start",
     "0/23/0/0/1,178/23/0/0/1,178/23/0/0/1,178/23/0/0/1,0/23/0/0/1,161/23/0/0/1,0/23/0/0/1"},
    {"passkey_retries_exhausted",
     "ADVERTISING,CONNECTED,PAIRING,CONNECTED,PAIRING,PAIRING,CONNECTED,PAIRING,CONNECTED,DISCONNECTING,DISCONNECTING,ADVERTISING,CONNECTED,PAIRING",
     "adv_start;timer_arm:30000;pairing_start;pairing_failed;pairing_start;mtu_reply:64;pairing_failed;pairing_start;pairing_failed;pairing_reject;disconnect:0x05;timer_arm:2000;timer_cancel;adv_start;timer_arm:30000;pairing_start",
     "0/23/0/0/0,161/23/0/0/0,161/23/1/0/0,161/23/1/0/0,161/23/2/0/0,161/64/2/0/0,161/64/2/0/0,161/64/3/0/0,161/64/3/0/0,161/64/3/0/0,161/64/3/0/0,0/23/0/0/0,161/23/0/0/0,161/23/1/0/0"},
    {"pairing_encryption_failure",
     "ADVERTISING,CONNECTED,PAIRING,PAIRING,PAIRING,DISCONNECTING,DISCONNECTING,ADVERTISING,ADVERTISING",
     "adv_start;timer_arm:30000;pairing_start;att_error:0x0030:05;pairing_confirm;disconnect:0x05;timer_arm:2000;link_reset;adv_start",
     "0/23/0/0/0,161/23/0/0/0,161/23/1/0/0,161/23/1/0/0,161/23/1/0/0,161/23/1/0/0,161/23/1/0/0,0/23/0/0/0,0/23/0/0/0"},
    {"ignored_events_in_idle_and_adv",
     "IDLE,IDLE,IDLE,IDLE,ADVERTISING,ADVERTISING,ADVERTISING,ADVERTISING,ADVERTISING,ADVERTISING,IDLE,IDLE",
     "adv_start;adv_stop",
     "0/23/0/0/0,0/23/0/0/0,0/23/0/0/0,0/23/0/0/0,0/23/0/0/0,0/23/0/0/0,0/23/0/0/0,0/23/0/0/0,0/23/0/0/0,0/23/0/0/0,0/23/0/0/0,0/23/0/0/0"},
    {"app_disconnect_while_pairing",
     "ADVERTISING,CONNECTED,PAIRING,DISCONNECTING,DISCONNECTING,ADVERTISING,CONNECTED,DISCONNECTING,ADVERTISING",
     "adv_start;timer_arm:30000;pairing_start;disconnect:0x13;timer_arm:2000;link_reset;adv_start;timer_arm:30000;disconnect:0x13;timer_arm:2000;timer_cancel;adv_start",
     "0/23/0/0/0,161/23/0/0/0,161/23/1/0/0,161/23/1/0/0,161/23/1/0/0,0/23/0/0/0,178/23/0/0/0,178/23/0/0/0,0/23/0/0/0"},
    {"ready_link_lost_resets_context",
     "ADVERTISING,CONNECTED,PAIRING,PAIRING,ENCRYPTED,READY,READY,ADVERTISING,CONNECTED,ENCRYPTED,READY,ADVERTISING",
     "adv_start;timer_arm:30000;pairing_start;pairing_confirm;timer_cancel;att_write_rsp:0x002a;timer_cancel;adv_start;timer_arm:30000;enc_request:a1;timer_cancel;att_write_rsp:0x002a;timer_cancel;adv_start",
     "0/23/0/0/0,161/23/0/0/0,161/23/1/0/0,161/23/1/0/0,161/23/1/0/1,161/23/1/1/1,161/23/1/1/1,0/23/0/0/1,161/23/0/0/1,161/23/0/0/1,161/23/0/1/1,0/23/0/0/1"},
};

static int check_trace(size_t i)
{
    static char s[2048], c[2048];
    run_trace(&TRACES[i], s, sizeof s, c, sizeof c);
    int ok = 1;
    if (strcmp(s, GOLDEN[i].states) != 0) {
        printf("  %s states\n    expected %s\n    actual   %s\n", GOLDEN[i].name, GOLDEN[i].states, s);
        ok = 0;
    }
    if (strcmp(hal_stub_calls(), GOLDEN[i].calls) != 0) {
        printf("  %s calls\n    expected %s\n    actual   %s\n", GOLDEN[i].name, GOLDEN[i].calls, hal_stub_calls());
        ok = 0;
    }
    if (strcmp(c, GOLDEN[i].ctx) != 0) {
        printf("  %s ctx\n    expected %s\n    actual   %s\n", GOLDEN[i].name, GOLDEN[i].ctx, c);
        ok = 0;
    }
    return ok;
}

TEST(full_session_new_phone) { CHECK(check_trace(0)); }
TEST(bonded_reconnect_and_link_loss) { CHECK(check_trace(1)); }
TEST(bonded_encryption_fails) { CHECK(check_trace(2)); }
TEST(passkey_retries_exhausted) { CHECK(check_trace(3)); }
TEST(pairing_encryption_failure) { CHECK(check_trace(4)); }
TEST(ignored_events_in_idle_and_adv) { CHECK(check_trace(5)); }
TEST(app_disconnect_while_pairing) { CHECK(check_trace(6)); }
TEST(ready_link_lost_resets_context) { CHECK(check_trace(7)); }

int main(void)
{
    RUN("golden", full_session_new_phone);
    RUN("golden", bonded_reconnect_and_link_loss);
    RUN("golden", bonded_encryption_fails);
    RUN("golden", passkey_retries_exhausted);
    RUN("golden", pairing_encryption_failure);
    RUN("golden", ignored_events_in_idle_and_adv);
    RUN("golden", app_disconnect_while_pairing);
    RUN("golden", ready_link_lost_resets_context);
    UNIT_EXIT();
}
