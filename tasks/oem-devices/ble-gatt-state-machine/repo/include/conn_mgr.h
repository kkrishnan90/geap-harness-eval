#ifndef CONN_MGR_H
#define CONN_MGR_H

/* Connection manager of the phone-as-key BLE peripheral (digital key module DKM-2).
 * Single connection. Driven by the BLE host task: every stack/app event is turned into a
 * cm_event_t and passed to cm_handle_event(). */

#include <stdbool.h>
#include <stdint.h>

#define CM_MTU_DEFAULT 23u
#define CM_MTU_MAX 247u
#define CM_MAX_PAIR_ATTEMPTS 3u
#define CM_SECURITY_TIMEOUT_MS 30000u   /* link must be encrypted within 30 s */
#define CM_DISCONNECT_TIMEOUT_MS 2000u  /* controller must confirm the disconnect */

#define CM_HCI_AUTH_FAILURE 0x05u
#define CM_HCI_CONN_TIMEOUT 0x08u
#define CM_HCI_REMOTE_USER_TERMINATED 0x13u
#define CM_ATT_ERR_INSUFFICIENT_AUTH 0x05u

typedef enum {
    CM_ST_IDLE = 0,
    CM_ST_ADVERTISING,
    CM_ST_CONNECTED,      /* link up, not encrypted */
    CM_ST_PAIRING,        /* SMP passkey pairing in progress */
    CM_ST_ENCRYPTED,      /* encrypted, key service notifications off */
    CM_ST_READY,          /* encrypted and the phone enabled notifications */
    CM_ST_DISCONNECTING,
    CM_ST_COUNT
} cm_state_t;

typedef enum {
    CM_EV_ADV_START = 0,  /* app: start advertising */
    CM_EV_ADV_STOP,       /* app: stop advertising */
    CM_EV_CONNECTED,      /* stack: link established (peer) */
    CM_EV_DISCONNECTED,   /* stack: link lost / disconnect complete (reason) */
    CM_EV_MTU_REQ,        /* stack: ATT exchange MTU request (mtu) */
    CM_EV_PAIR_REQ,       /* stack: SMP pairing request */
    CM_EV_PASSKEY_RESULT, /* stack: passkey comparison done (status 0 = match) */
    CM_EV_ENC_CHANGED,    /* stack: encryption change (status 0 = encrypted) */
    CM_EV_CCCD_WRITE,     /* stack: write to the key service CCCD (handle, value) */
    CM_EV_TIMEOUT,        /* supervision timer expired */
    CM_EV_APP_DISCONNECT, /* app: terminate the link */
    CM_EV_COUNT
} cm_event_type_t;

typedef struct {
    cm_event_type_t type;
    uint8_t peer[6];
    uint16_t mtu;
    uint8_t status;
    uint8_t reason;
    uint16_t handle;
    uint16_t value;
} cm_event_t;

typedef struct {
    cm_state_t state;
    uint8_t peer[6];
    bool has_peer;
    uint16_t mtu;
    uint8_t pair_attempts;
    bool notify_enabled;
} cm_ctx_t;

void cm_init(cm_ctx_t *ctx);
cm_state_t cm_state(const cm_ctx_t *ctx);
void cm_handle_event(cm_ctx_t *ctx, const cm_event_t *ev);
const char *cm_state_str(cm_state_t s);

#endif
