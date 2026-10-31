# body-can-decode

Signal decoding library for the body-domain gateway ECU (BCM-GW). It turns raw
CAN frames into physical values using signal definitions generated from the
vehicle DBC (`tools/dbcgen` emits `can_signal_t` tables; for bench tooling we
also parse single `SG_` lines at runtime with `dbc_lite`).

## Modules

| File | Purpose |
| --- | --- |
| `include/candec.h`, `src/candec.c` | Bit-level signal extraction, sign handling, scaling |
| `include/dbc_lite.h`, `src/dbc_lite.c` | Parser for one DBC `SG_` line into a `can_signal_t` |
| `include/e2e.h`, `src/crc8_sae.c` | SAE J1850 CRC-8 used by AUTOSAR E2E profile 1 |
| `include/e2e.h`, `src/alive_counter.c` | Rolling (alive) counter supervision |

## Signal conventions (same as the DBC format)

* `@1` = Intel (little endian). `start_bit` is the position of the **LSB**.
  Bits are numbered `byte * 8 + bit`, bit 0 = least significant bit of the byte.
* `@0` = Motorola (big endian). `start_bit` is the position of the **MSB**
  in the same numbering ("sawtooth" numbering, as shown by CANdb++).
* `+` unsigned, `-` signed two's complement of `length` bits.
* physical = raw_value * factor + offset

## Conventions

* C11, no dynamic allocation, no libc beyond `<stdint.h>`, `<stdbool.h>`,
  `<string.h>`, `<stdlib.h>`, `<math.h>` (code is shared with the ECU build).
* Functions return `CAN_OK` (0) or a negative `CAN_ERR_*` code; outputs are
  written only on success.
* Public headers are frozen for this release: do not change signatures.
* Build and test: `make test` (clang, `-std=c11 -Wall -Wextra -Werror`).
