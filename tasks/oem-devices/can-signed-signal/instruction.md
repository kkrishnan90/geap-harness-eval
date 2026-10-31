# BCMGW-2291: Negative temperatures and big-endian signals decode wrong on the gateway

**Component:** body-can-decode (`src/candec.c`) · **Priority:** Critical · **Type:** Bug
**Found by:** HIL bench, chassis CAN replay of winter test drive (log `WT-2026-01-17`)

## Context

The body gateway decodes chassis CAN signals with `libcandec`. Signal tables are
generated from the vehicle DBC; signal conventions are documented in the
README (Intel `@1`: `start_bit` = LSB, Motorola `@0`: `start_bit` = MSB in
sawtooth numbering, `-` = two's complement).

During the winter test replay the gateway reported a coolant temperature of
`6513.6 degC` instead of `-40.0 degC`, and every signal of the ESC
(stability control) messages, which use Motorola byte order, is garbage or is
rejected with `CAN_ERR_RANGE` as soon as it crosses a byte boundary.

## Problems observed

1. `can_decode_physical()` ignores `is_signed`: negative signed signals are
   scaled as if they were unsigned.
2. `can_decode_value()` does not sign-extend signed signals longer than 32 bits.
3. Motorola signals spanning more than one byte are extracted from the wrong
   bits: after bit 0 of a byte, extraction must continue at bit 7 of the
   **next** byte (DBC sawtooth order).
4. The payload range check uses the Intel formula for Motorola signals, so
   valid big-endian signals are rejected (e.g. `7|16@0+` in a 2-byte frame) and
   some that run off the payload are accepted.

## Expected behaviour

- `can_extract_raw()` returns the unsigned raw bit pattern, right-aligned, for
  both byte orders and any length 1..64.
- `can_decode_value()` and `can_decode_physical()` sign-extend (two's
  complement of exactly `length` bits) when `is_signed` is set, for any length
  1..64 (a 1-bit signed signal is 0 or -1; a 64-bit one covers `INT64_MIN`).
  Unsigned signals stay unsigned.
- `physical = value * factor + offset`.
- `CAN_ERR_RANGE` is returned if **any** bit of the signal lies outside the
  first `dlc` bytes, for either byte order. Outputs are written only on
  `CAN_OK`. The other error codes keep their current meaning and precedence
  (`CAN_ERR_NULL`, then `CAN_ERR_DLC`, then `CAN_ERR_LENGTH`, then range).

Examples (bytes are listed `data[0]` first):

| Signal | Payload | Expected |
| --- | --- | --- |
| `16\|16@1- (0.1,0)` | `00 00 70 FE ..` | physical `-40.0` |
| `7\|16@0+ (0.25,0)` | `1F 40` | raw `0x1F40`, physical `2000.0` |
| `3\|12@0- (0.5,0)` | `AF 9C ..` | raw `0xF9C`, value `-100`, physical `-50.0` |
| `0\|2@0+` | `01 80` (dlc 2) | raw `3`; with dlc 1: `CAN_ERR_RANGE` |

## Constraints

- Public headers (`include/*.h`) are frozen: no signature or constant changes.
- C11, no dynamic allocation; code must build warning-free with
  `clang -std=c11 -Wall -Wextra -Werror`.
- Existing tests must keep passing (`make test`).
