# @numbering/core

Telephone-number helpers shared by subscriber provisioning, the SMS gateway
and CDR mediation. Every MSISDN that enters our systems is stored in E.164
(`+<country code><national significant number>`, digits only after the `+`).

## Modules

| File | Purpose |
| --- | --- |
| `src/dialplans.ts` | Per-region dialling plans (country code, trunk prefix, international prefix, NSN lengths) |
| `src/e164.ts` | `normalizeE164()` – user/CRM input to E.164; `formatInternational()` |
| `src/msisdn.ts` | Masking for logs/CDR exports, MSISDN range helpers |
| `src/porting.ts` | Mobile number portability (MNP) routing-number lookups |
| `src/index.ts` | Public entry point – everything exported here is public API |

## Conventions

* Node.js 24, no dependencies, no build step: sources are TypeScript run
  directly by Node's type stripping. Only *erasable* TypeScript is allowed
  (no `enum`, `namespace`, parameter properties). Import with `.ts` extensions.
* Functions that parse user input never throw; they return a result object
  (`{ ok: true, ... } | { ok: false, error }`).
* Error codes are consumed by the provisioning UI; do not rename them.
* Tests use `node:test` + `node:assert/strict`:

```
npm test        # or: node --test test/*.test.ts
```
