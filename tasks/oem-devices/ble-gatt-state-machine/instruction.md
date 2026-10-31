# DKM-1407: Refactor `conn_mgr.c` into a table-driven state machine

**Component:** dkm2-ble-periph / connection manager · **Priority:** Medium · **Type:** Refactoring (+1 design fix)

## Context

`src/conn_mgr.c` is a nested `switch (state) { switch (event) … }` that has
grown with every feature: the MTU, disconnect and link-loss handling is
copy-pasted into four or five states, and safety review cannot compare it
against the design state chart in `docs/conn_fsm.md`. For the ASIL-B
re-assessment the connection manager must become **table-driven**: one
`const` transition table that reviewers can diff against the chart, a
generic dispatcher, and named actions behind replaceable hooks (the HIL rig
uses them for fault injection).

## Scope

1. Add `include/gatt_fsm.h` with exactly this API (names and enumerator order
   are fixed — the HIL tooling and the UDS diagnostics decode them):

```c
#include <stdbool.h>
#include <stddef.h>
#include "conn_mgr.h"

typedef enum {
    GFSM_GUARD_NONE = 0, GFSM_GUARD_PEER_BONDED, GFSM_GUARD_PAIR_ATTEMPTS_LEFT,
    GFSM_GUARD_STATUS_OK, GFSM_GUARD_CCCD_ENABLE, GFSM_GUARD_COUNT
} gfsm_guard_t;

typedef enum {
    GFSM_ACT_NONE = 0, GFSM_ACT_ADV_START, GFSM_ACT_ADV_STOP, GFSM_ACT_CONNECT_NEW,
    GFSM_ACT_CONNECT_BONDED, GFSM_ACT_MTU_REPLY, GFSM_ACT_PAIR_START, GFSM_ACT_PAIR_REJECT,
    GFSM_ACT_PASSKEY_CONFIRM, GFSM_ACT_PASSKEY_FAILED, GFSM_ACT_ENC_DONE, GFSM_ACT_ENC_DONE_BOND,
    GFSM_ACT_AUTH_FAIL_DISCONNECT, GFSM_ACT_ATT_INSUFFICIENT_AUTH, GFSM_ACT_CCCD_WRITE,
    GFSM_ACT_TIMEOUT_DISCONNECT, GFSM_ACT_APP_DISCONNECT, GFSM_ACT_LINK_LOST, GFSM_ACT_LINK_RESET,
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
typedef void (*gfsm_observer_fn)(const gfsm_transition_t *t, const cm_ctx_t *ctx,
                                 const cm_event_t *ev, void *user);

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
```

2. Semantics:
   - `gfsm_table()` returns the one static `const` table and stores its row
     count in `*count` (if non-NULL). It contains exactly the rows of
     `docs/conn_fsm.md` (no more, no fewer); rows with the same
     (from, event) keep the chart's relative order (guarded rows first).
   - `gfsm_guard_holds()` implements the chart's guard table
     (`GFSM_GUARD_NONE` is always true).
   - `gfsm_find()` returns the first row in table order whose `from` equals
     `ctx->state`, whose `event` equals `ev->type` and whose guard holds;
     `NULL` if none (or `ev` is NULL / out of range).
   - `gfsm_dispatch()`: finds the row; if none, returns `NULL` and has no side
     effects at all. Otherwise runs the row's action (the hook installed with
     `gfsm_set_action_hook`, else `gfsm_default_action(action)`; nothing for
     `GFSM_ACT_NONE`) **while `ctx->state` is still the old state**, then sets
     `ctx->state = row->to`, then calls the observer (if set) with the row,
     the updated ctx, the event and the observer's `user` pointer, and returns
     the row pointer (a pointer into the table). Internal transitions
     (`to == from`) also run the action and notify the observer.
   - `gfsm_default_action()` returns the built-in implementation of every
     action of the chart's action table (non-NULL for every action except
     `GFSM_ACT_NONE`, which returns NULL). `gfsm_set_action_hook(a, NULL)`
     restores the default.
   - Name functions return the enumerator name without prefix (e.g.
     `"DISCONNECTING"`, `"PASSKEY_RESULT"`, `"PAIR_ATTEMPTS_LEFT"`,
     `"AUTH_FAIL_DISCONNECT"`, `"NONE"`) and `"?"` for out-of-range values.
     `cm_state_str()` returns the same strings as `gfsm_state_name()`.
3. `conn_mgr.c` becomes a thin facade: `cm_init`, `cm_state`,
   `cm_state_str` and `cm_handle_event` (which delegates to
   `gfsm_dispatch`). It must not call `hal_*` functions itself. No code in
   `src/` may dispatch on the state with `switch`/`case CM_ST_…` labels any
   more — states are handled only through the table.
4. Behaviour must be **identical** to the current implementation (HAL calls
   and their order, context updates, bond store, ignored events), with one
   exception: the code currently disagrees with the chart for
   PAIRING + TIMEOUT (it sends `pairing_failed` and goes back to CONNECTED).
   The chart is right: row 20 (`TIMEOUT_DISCONNECT` → DISCONNECTING).

## Constraints

- `include/conn_mgr.h` is frozen. C11, no dynamic allocation.
- `make test` must pass; the existing tests describe the current behaviour.
