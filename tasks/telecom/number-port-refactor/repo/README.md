# @porting/gateway

Intake validation for UK number portability requests before they are sent to
the central porting hub:

* **mobile** ports (customer gives a PAC, `src/handlers/mobile.ts`)
* **fixed-line** ports (geographic 01/02 numbers, account number as
  authorisation, `src/handlers/fixed.ts`)
* **bulk** ports submitted by wholesale partners as CSV batches
  (`src/handlers/bulk.ts`)

Each handler returns a `Decision`: `accepted` plus the list of rejection codes
that the hub's reason-code mapping understands (`NUMBER_FORMAT`,
`UNKNOWN_OPERATOR`, `SAME_OPERATOR`, `AUTH_CODE`, `PORT_DATE`, `DUPLICATE`).

## Layout

| Path | Purpose |
| --- | --- |
| `src/model.ts` | Request, decision and context types |
| `src/handlers/*.ts` | One handler per channel |
| `src/calendar.ts` | Business-day arithmetic (weekends + bank holidays) |
| `src/operators.ts` | Operator registry (which operator offers which service) |
| `src/audit.ts` | Audit line formatting for the porting log |
| `src/index.ts` | Public entry point |

## Conventions

* Node 24 with TypeScript type stripping: erasable syntax only (no `enum`,
  `namespace`, parameter properties). No dependencies.
* Dates are `YYYY-MM-DD` strings in UK local date; no `Date.now()` inside
  validation (the caller passes `today` in the context).
* Handlers are pure functions of (request, context).
* Tests: `npm test` (`node --test test/*.test.ts`).
