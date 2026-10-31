# PORT-2210: Consolidate porting validation into one shared rules module

**Component:** `@porting/gateway` · **Priority:** Medium · **Type:** Tech debt / Refactor

## Context

The three intake channels (`src/handlers/mobile.ts`, `fixed.ts`, `bulk.ts`)
each carry their own copy of the porting validation rules. The copies have
drifted, and the porting hub keeps bouncing requests that we accepted (and we
reject valid ones). Known drifts include: the mobile handler stops at the
first problem, PAC/account checks disagree on case, the fixed handler counts
calendar days and allows 31, the bulk handler ignores bank holidays and
misses duplicates inside one batch, and the geographic number pattern
differs per channel.

Refactor so that every channel delegates to a single rules module. The
behaviour below is the **intended** one (agreed with the porting hub team);
where a handler differs today, the handler is wrong.

## Target design

Create `src/rules/index.ts` exporting exactly:

```ts
export type RuleId = 'NUMBER_FORMAT' | 'UNKNOWN_OPERATOR' | 'SAME_OPERATOR' | 'AUTH_CODE' | 'PORT_DATE' | 'DUPLICATE';

export interface PortCandidate {
  kind: ServiceKind;        // 'mobile' | 'fixed'
  number: string;           // normalised (all whitespace removed)
  donor: string;
  recipient: string;
  authCode: string;         // mobile: PAC, fixed: account number; trimmed
  requestedDate: string;    // as given
}

export interface Rule {
  readonly id: string;
  check(candidate: PortCandidate, ctx: PortingContext): boolean; // true = passes
}

export const DEFAULT_RULES: readonly Rule[];   // in canonical order (table below)
export function evaluate(candidate: PortCandidate, ctx: PortingContext, rules?: readonly Rule[]): Decision;
export function normalizeNumber(raw: string): string;   // removes all whitespace
```

- `evaluate` runs **every** rule (no short-circuit) and returns
  `{ accepted, rejections }` with the ids of the failing rules **in the order
  of the rule list** (default `DEFAULT_RULES`).
- Each handler gets an optional last parameter `rules: readonly Rule[] = DEFAULT_RULES`
  and contains no rule logic of its own; it only maps its request to a
  `PortCandidate` and calls `evaluate`:
  - `validateMobilePort(req, ctx, rules?)` - `number` from `msisdn`, `authCode` from `pac`
  - `validateFixedPort(req, ctx, rules?)` - `number` from `number`, `authCode` from `accountNumber`
  - `validateBulkPort(batch, ctx, rules?)` - per item, with `kind` from the item. For
    each item, the numbers of all **earlier items of the same batch** (whatever
    their outcome) are treated as open ports, i.e. the item is evaluated with a
    context whose `openPorts` = `ctx.openPorts` plus those numbers (normalised).
    The caller's `ctx` must not be mutated. `results[i].number` stays as submitted.

## Intended rules (canonical order)

| # | Id | Passes when |
| --- | --- | --- |
| 1 | `NUMBER_FORMAT` | mobile: `^\+447\d{9}$`; fixed: `^\+44[12]\d{8,9}$` (after normalisation) |
| 2 | `UNKNOWN_OPERATOR` | donor **and** recipient are in the registry **and** offer the candidate's service kind (`operators.supports(id, kind)`) |
| 3 | `SAME_OPERATOR` | donor !== recipient |
| 4 | `AUTH_CODE` | mobile PAC `^[A-Z]{3}\d{6}$`, fixed account `^[A-Z0-9]{6,12}$`, both **case-insensitive**, on the trimmed value |
| 5 | `PORT_DATE` | `requestedDate` is a valid `YYYY-MM-DD`, is a business day (weekends and `ctx.holidays` excluded), is at least **1** (mobile) / **2** (fixed) business days after `ctx.today` (count of business days d with today < d <= requested), and at most **30 calendar days** after `ctx.today` |
| 6 | `DUPLICATE` | the normalised number is not in `openPorts` |

Use the existing helpers in `src/calendar.ts` and `src/operators.ts`.
Export the new module's public API from `src/index.ts` as well.

## Acceptance criteria

- All three channels give identical decisions for equivalent input, per the
  table above, with all failing rules reported in canonical order.
- A custom rule list passed to any handler fully replaces the default rules
  for that call (this is how the hub's temporary blocklists will be plugged in).
- Existing tests keep passing; public types in `src/model.ts` are unchanged.

## Constraints

- No dependencies; erasable TypeScript only (Node 24 type stripping).
- Keep handler names and existing parameters; only the optional `rules`
  parameter is added.
