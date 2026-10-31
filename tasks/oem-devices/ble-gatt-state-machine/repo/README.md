# dkm2-ble-periph

BLE peripheral firmware components of the DKM-2 digital key module
(phone-as-key). The phone connects, pairs once with a passkey shown on the
instrument cluster, and afterwards reconnects with the bonded key; the key
service is only usable on an encrypted link.

## Modules

| File | Purpose |
| --- | --- |
| `include/conn_mgr.h`, `src/conn_mgr.c` | Connection manager (state machine, see `docs/conn_fsm.md`) |
| `include/hal_ble.h`, `src/hal_ble_stub.c` | BLE HAL; the host build uses a stub that records calls |
| `include/bond_store.h`, `src/bond_store.c` | Bonded phones (LRU, 8 entries) |
| `include/adv_data.h`, `src/adv_data.c` | Advertising payload builder |
| `include/evt_log.h`, `src/evt_log.c` | Diagnostic ring log (UDS 0x22 F1A0) |

## Conventions

* C11, no dynamic allocation, no recursion (MISRA-derived rules of the
  vehicle SW platform).
* `include/conn_mgr.h` is the API used by the BLE host task and the UDS
  diagnostics; it is frozen (types, enums and functions).
* Every file in `src/` is compiled for the host and for the target.
* Build and test on the host: `make test` (clang, `-std=c11 -Wall -Wextra -Werror`).
