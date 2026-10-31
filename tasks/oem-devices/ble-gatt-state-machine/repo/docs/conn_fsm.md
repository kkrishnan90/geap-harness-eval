# DKM-2 connection manager: state chart (design baseline v1.4)

Single BLE connection, peripheral role. States and events are the `CM_ST_*` /
`CM_EV_*` enums of `include/conn_mgr.h`.

## Transitions

Rows are evaluated top to bottom; the first row whose *from* state and *event*
match and whose *guard* holds is taken. An event without a matching row is
ignored (no state change, no side effects). The action runs before the state
changes. `-` means no guard.

| # | from | event | guard | to | action |
|---|------|-------|-------|----|--------|
| 1 | IDLE | ADV_START | - | ADVERTISING | ADV_START |
| 2 | ADVERTISING | ADV_STOP | - | IDLE | ADV_STOP |
| 3 | ADVERTISING | CONNECTED | PEER_BONDED | CONNECTED | CONNECT_BONDED |
| 4 | ADVERTISING | CONNECTED | - | CONNECTED | CONNECT_NEW |
| 5 | CONNECTED | MTU_REQ | - | CONNECTED | MTU_REPLY |
| 6 | CONNECTED | PAIR_REQ | PAIR_ATTEMPTS_LEFT | PAIRING | PAIR_START |
| 7 | CONNECTED | PAIR_REQ | - | DISCONNECTING | PAIR_REJECT |
| 8 | CONNECTED | ENC_CHANGED | STATUS_OK | ENCRYPTED | ENC_DONE |
| 9 | CONNECTED | ENC_CHANGED | - | DISCONNECTING | AUTH_FAIL_DISCONNECT |
| 10 | CONNECTED | CCCD_WRITE | - | CONNECTED | ATT_INSUFFICIENT_AUTH |
| 11 | CONNECTED | TIMEOUT | - | DISCONNECTING | TIMEOUT_DISCONNECT |
| 12 | CONNECTED | APP_DISCONNECT | - | DISCONNECTING | APP_DISCONNECT |
| 13 | CONNECTED | DISCONNECTED | - | ADVERTISING | LINK_LOST |
| 14 | PAIRING | MTU_REQ | - | PAIRING | MTU_REPLY |
| 15 | PAIRING | PASSKEY_RESULT | STATUS_OK | PAIRING | PASSKEY_CONFIRM |
| 16 | PAIRING | PASSKEY_RESULT | - | CONNECTED | PASSKEY_FAILED |
| 17 | PAIRING | ENC_CHANGED | STATUS_OK | ENCRYPTED | ENC_DONE_BOND |
| 18 | PAIRING | ENC_CHANGED | - | DISCONNECTING | AUTH_FAIL_DISCONNECT |
| 19 | PAIRING | CCCD_WRITE | - | PAIRING | ATT_INSUFFICIENT_AUTH |
| 20 | PAIRING | TIMEOUT | - | DISCONNECTING | TIMEOUT_DISCONNECT |
| 21 | PAIRING | APP_DISCONNECT | - | DISCONNECTING | APP_DISCONNECT |
| 22 | PAIRING | DISCONNECTED | - | ADVERTISING | LINK_LOST |
| 23 | ENCRYPTED | MTU_REQ | - | ENCRYPTED | MTU_REPLY |
| 24 | ENCRYPTED | CCCD_WRITE | CCCD_ENABLE | READY | CCCD_WRITE |
| 25 | ENCRYPTED | CCCD_WRITE | - | ENCRYPTED | CCCD_WRITE |
| 26 | ENCRYPTED | APP_DISCONNECT | - | DISCONNECTING | APP_DISCONNECT |
| 27 | ENCRYPTED | DISCONNECTED | - | ADVERTISING | LINK_LOST |
| 28 | READY | MTU_REQ | - | READY | MTU_REPLY |
| 29 | READY | CCCD_WRITE | CCCD_ENABLE | READY | CCCD_WRITE |
| 30 | READY | CCCD_WRITE | - | ENCRYPTED | CCCD_WRITE |
| 31 | READY | APP_DISCONNECT | - | DISCONNECTING | APP_DISCONNECT |
| 32 | READY | DISCONNECTED | - | ADVERTISING | LINK_LOST |
| 33 | DISCONNECTING | DISCONNECTED | - | ADVERTISING | LINK_LOST |
| 34 | DISCONNECTING | TIMEOUT | - | ADVERTISING | LINK_RESET |

## Guards

| guard | holds when |
|-------|-----------|
| PEER_BONDED | the event's `peer` is in the bond store |
| PAIR_ATTEMPTS_LEFT | `ctx->pair_attempts < CM_MAX_PAIR_ATTEMPTS` |
| STATUS_OK | `ev->status == 0` |
| CCCD_ENABLE | `(ev->value & 0x0001) != 0` (notifications bit) |

## Actions (HAL calls in this order)

| action | effect |
|--------|--------|
| ADV_START | `hal_adv_start()` |
| ADV_STOP | `hal_adv_stop()` |
| CONNECT_NEW | store peer; `hal_timer_arm(CM_SECURITY_TIMEOUT_MS)` |
| CONNECT_BONDED | store peer; `hal_timer_arm(CM_SECURITY_TIMEOUT_MS)`; `hal_enc_request(peer)` |
| MTU_REPLY | mtu = clamp(ev->mtu, 23, 247), store it; `hal_mtu_reply(mtu)` |
| PAIR_START | `pair_attempts++`; `hal_pairing_start()` |
| PAIR_REJECT | `hal_pairing_reject()`; `hal_disconnect(0x05)`; `hal_timer_arm(CM_DISCONNECT_TIMEOUT_MS)` |
| PASSKEY_CONFIRM | `hal_pairing_confirm()` |
| PASSKEY_FAILED | `hal_pairing_failed()` |
| ENC_DONE | `hal_timer_cancel()` |
| ENC_DONE_BOND | `hal_timer_cancel()`; add peer to the bond store |
| AUTH_FAIL_DISCONNECT | `hal_disconnect(0x05)`; `hal_timer_arm(CM_DISCONNECT_TIMEOUT_MS)` |
| ATT_INSUFFICIENT_AUTH | `hal_att_error(ev->handle, 0x05)` |
| CCCD_WRITE | `notify_enabled = CCCD_ENABLE`; `hal_att_write_rsp(ev->handle)` |
| TIMEOUT_DISCONNECT | `hal_disconnect(0x08)`; `hal_timer_arm(CM_DISCONNECT_TIMEOUT_MS)` |
| APP_DISCONNECT | `hal_disconnect(0x13)`; `hal_timer_arm(CM_DISCONNECT_TIMEOUT_MS)` |
| LINK_LOST | `hal_timer_cancel()`; reset link context; `hal_adv_start()` |
| LINK_RESET | `hal_link_reset()`; reset link context; `hal_adv_start()` |

"Reset link context" = peer cleared, `has_peer = false`, mtu 23,
`pair_attempts = 0`, `notify_enabled = false`.
