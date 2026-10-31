# NUM-882: `normalizeE164()` produces wrong numbers for international dialling and some regions

**Component:** `@numbering/core` – `src/e164.ts` · **Priority:** Critical · **Type:** Bug

## Context

Subscriber provisioning and the SMS gateway store every number in E.164.
Since the CRM migration we see failed SMS deliveries and rejected port-in
orders. Examples from the incident channel:

| Captured in | Typed as | Expected | We stored / returned |
| --- | --- | --- | --- |
| US | `+1 (415) 555-2671` | `+14155552671` | `UNKNOWN_REGION` |
| US | `1-415-555-2671` | `+14155552671` | `INVALID_LENGTH` |
| IT | `06 6982 1234` | `+390669821234` | `+39669821234` (wrong number!) |
| GB | `0044 20 7946 0958` | `+442079460958` | `INVALID_LENGTH` |
| FR | `+44 (0)20 7946 0958` | `+442079460958` | `INVALID_LENGTH` |

## Required behaviour of `normalizeE164(input, defaultRegion)`

The dialling plans in `src/dialplans.ts` are correct and are the source of truth.

1. **Separators.** Whitespace, `-`, `.`, `/`, `(` and `)` are ignored. Any other
   non-digit character (letters, `#`, `*`, a `+` that is not the first
   character...) gives `INVALID_FORMAT`; so does empty input.
2. **International input** is either `+` followed by the number, or the
   **international prefix of `defaultRegion`** (e.g. `00` for GB/DE,
   `011` for US, `0011` for AU, `010` for JP) followed by the number.
   * The country code is 1, 2 or 3 digits and is matched against the dialling
     plans (E.164 country codes are prefix-free, so at most one plan matches).
     No match: `UNKNOWN_REGION`.
   * A bracketed trunk prefix `(0)` written in an international number (as in
     `+44 (0)20 7946 0958`) is not part of the number and is dropped.
   * The rest is the national significant number (NSN), used as-is.
3. **National input** (anything else) uses the plan of `defaultRegion`
   (case-insensitive; unknown region: `UNKNOWN_REGION`). If the plan has a
   `trunkPrefix` and the number starts with it, that prefix is removed. If the
   plan's `trunkPrefix` is `null` (e.g. IT, SG) nothing is removed; Italian
   fixed-line numbers keep their leading `0` in E.164.
4. The NSN length must be one of the plan's `nsnLengths`, otherwise
   `INVALID_LENGTH`.
5. Success result: `{ ok: true, e164: '+<cc><nsn>', region, nationalNumber: <nsn> }`
   where `region` is the region of the matched plan (for international input,
   the region the number belongs to, not `defaultRegion`).

## Acceptance criteria

- Every row of the table above produces the expected value.
- `011 44 20 7946 0958` captured in the US normalises to `+442079460958` with region `GB`.
- `00 999 1234567` captured in GB returns `UNKNOWN_REGION`.
- Existing tests (`npm test`) stay green.

## Constraints

- Keep the public API in `src/index.ts` (names, signatures, result shapes, error codes) unchanged.
- No dependencies; erasable TypeScript only (see README).
