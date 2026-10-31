#include "unit.h"
#include "cm_helpers.h"

TEST(advertise_and_stop)
{
    cm_ctx_t c;
    fresh(&c);
    CHECK_EQ_INT(CM_ST_IDLE, cm_state(&c));
    send(&c, CM_EV_ADV_START);
    CHECK_EQ_INT(CM_ST_ADVERTISING, cm_state(&c));
    send(&c, CM_EV_ADV_START); /* ignored */
    send(&c, CM_EV_ADV_STOP);
    CHECK_EQ_INT(CM_ST_IDLE, cm_state(&c));
    CHECK_CALLS("adv_start;adv_stop");
}

TEST(first_pairing_bonds_the_phone)
{
    cm_ctx_t c;
    fresh(&c);
    send(&c, CM_EV_ADV_START);
    send_connect(&c, PHONE_A);
    send_mtu(&c, 185);
    send(&c, CM_EV_PAIR_REQ);
    send_status(&c, CM_EV_PASSKEY_RESULT, 0);
    send_status(&c, CM_EV_ENC_CHANGED, 0);
    send_cccd(&c, 0x002A, 0x0001);
    CHECK_EQ_INT(CM_ST_READY, cm_state(&c));
    CHECK(bond_store_contains(PHONE_A));
    CHECK_EQ_INT(185, c.mtu);
    CHECK(c.notify_enabled);
    CHECK_CALLS("adv_start;timer_arm:30000;mtu_reply:185;pairing_start;pairing_confirm;timer_cancel;att_write_rsp:0x002a");
}

TEST(bonded_phone_reencrypts)
{
    cm_ctx_t c;
    fresh(&c);
    bond_store_add(PHONE_B);
    send(&c, CM_EV_ADV_START);
    send_connect(&c, PHONE_B);
    send_status(&c, CM_EV_ENC_CHANGED, 0);
    CHECK_EQ_INT(CM_ST_ENCRYPTED, cm_state(&c));
    CHECK_CALLS("adv_start;timer_arm:30000;enc_request:b2;timer_cancel");
}

TEST(key_service_needs_encryption)
{
    cm_ctx_t c;
    fresh(&c);
    send(&c, CM_EV_ADV_START);
    send_connect(&c, PHONE_A);
    hal_stub_reset();
    send_cccd(&c, 0x002A, 0x0001);
    CHECK_EQ_INT(CM_ST_CONNECTED, cm_state(&c));
    CHECK_CALLS("att_error:0x002a:05");
}

TEST(mtu_is_clamped)
{
    cm_ctx_t c;
    fresh(&c);
    send(&c, CM_EV_ADV_START);
    send_connect(&c, PHONE_A);
    hal_stub_reset();
    send_mtu(&c, 517);
    send_mtu(&c, 10);
    CHECK_CALLS("mtu_reply:247;mtu_reply:23");
    CHECK_EQ_INT(23, c.mtu);
}

TEST(security_timeout_disconnects)
{
    cm_ctx_t c;
    fresh(&c);
    send(&c, CM_EV_ADV_START);
    send_connect(&c, PHONE_A);
    hal_stub_reset();
    send(&c, CM_EV_TIMEOUT);
    CHECK_EQ_INT(CM_ST_DISCONNECTING, cm_state(&c));
    send(&c, CM_EV_DISCONNECTED);
    CHECK_EQ_INT(CM_ST_ADVERTISING, cm_state(&c));
    CHECK(!c.has_peer);
    CHECK_CALLS("disconnect:0x08;timer_arm:2000;timer_cancel;adv_start");
}

TEST(three_wrong_passkeys_then_reject)
{
    cm_ctx_t c;
    fresh(&c);
    send(&c, CM_EV_ADV_START);
    send_connect(&c, PHONE_A);
    for (int i = 0; i < 3; i++) {
        send(&c, CM_EV_PAIR_REQ);
        CHECK_EQ_INT(CM_ST_PAIRING, cm_state(&c));
        send_status(&c, CM_EV_PASSKEY_RESULT, 1);
        CHECK_EQ_INT(CM_ST_CONNECTED, cm_state(&c));
    }
    hal_stub_reset();
    send(&c, CM_EV_PAIR_REQ);
    CHECK_EQ_INT(CM_ST_DISCONNECTING, cm_state(&c));
    CHECK_CALLS("pairing_reject;disconnect:0x05;timer_arm:2000");
    CHECK(!bond_store_contains(PHONE_A));
}

TEST(disconnect_timeout_resets_link)
{
    cm_ctx_t c;
    fresh(&c);
    send(&c, CM_EV_ADV_START);
    send_connect(&c, PHONE_A);
    send(&c, CM_EV_APP_DISCONNECT);
    hal_stub_reset();
    send(&c, CM_EV_TIMEOUT);
    CHECK_EQ_INT(CM_ST_ADVERTISING, cm_state(&c));
    CHECK_CALLS("link_reset;adv_start");
}

TEST(state_names)
{
    CHECK(strcmp(cm_state_str(CM_ST_READY), "READY") == 0);
    CHECK(strcmp(cm_state_str(CM_ST_DISCONNECTING), "DISCONNECTING") == 0);
}

int main(void)
{
    RUN("conn", advertise_and_stop);
    RUN("conn", first_pairing_bonds_the_phone);
    RUN("conn", bonded_phone_reencrypts);
    RUN("conn", key_service_needs_encryption);
    RUN("conn", mtu_is_clamped);
    RUN("conn", security_timeout_disconnects);
    RUN("conn", three_wrong_passkeys_then_reject);
    RUN("conn", disconnect_timeout_resets_link);
    RUN("conn", state_names);
    UNIT_EXIT();
}
