# INT-1543: Implement FHIR search parameter semantics (modifiers, prefixes, tokens, sort)

**Component:** `@clinic/fhir-lite` (`src/search/`) · **Priority:** High · **Type:** Story

## Context

The integration engine test harness replays FHIR queries recorded from the
EHR vendor against our in-memory store. Most replays currently return wrong
results because `search()` only does a prefix match on string parameters and
plain equality on everything else, silently ignores parameters it does not
know, and has no `_sort`. A query that the EHR would reject (typo in a
parameter name) returns *all* patients here, which already hid a bug in the
kiosk check-in flow.

Implement the subset of FHIR R4 search below for the parameters already
declared in `src/search/registry.ts` (Patient: `_id`, `family`, `given`,
`name`, `gender`, `birthdate`, `identifier`; Observation: `_id`, `status`,
`code`, `subject`, `date`). `search(store, resourceType, query)` keeps its
signature and returns a searchset `Bundle` or an `OperationOutcome`.

## Required semantics

**General**
- The query string is URL-decoded (`%7C` = `|`, `+` = space). A leading `?` is allowed.
- Commas in a value mean OR: `gender=male,other`. Repeating a parameter means
  AND: `date=ge2024-01-01&date=lt2024-02-01`. Modifiers combine with commas.
- A resource that has no value for the element never matches a value-based
  criterion (this includes `ne`). Only `:missing` matches absent elements.
- Without `_sort`, results stay in store insertion order.

**string** (`family`, `given`, `name`)
- default: case-insensitive *starts-with* (current behaviour)
- `:exact`: case-sensitive equality with the whole element value
- `:contains`: case-insensitive substring

**token** (`_id`, `gender`, `status`, `identifier`, `code`) - case-sensitive
- `code`: matches the code in any system
- `system|code`: both match
- `|code`: the code with **no** system
- `system|`: any code in that system

**reference** (`subject`): `Patient/p1` matches that exact reference; a bare
id `p1` matches a reference to any type with that id.

**date** (`birthdate`, `date`)
- Search value: optional prefix `eq|ne|lt|gt|le|ge|sa|eb` (default `eq`) then
  `YYYY`, `YYYY-MM`, `YYYY-MM-DD` or `YYYY-MM-DDThh:mm[:ss]` followed by `Z`
  or `+hh:mm`/`-hh:mm` (a time without zone is invalid).
- Every value (search value and stored element) denotes the half-open UTC
  interval it covers at its precision: a year, month, day, minute or second.
  Dates without time are UTC days. Stored dateTimes with an offset are
  converted to UTC (`2024-03-01T23:30:00-02:00` is on 2024-03-02 UTC).
- With element range `R = [rs, re)` and search range `P = [ps, pe)`:

  | prefix | matches when |
  | --- | --- |
  | `eq` | `rs >= ps` and `re <= pe` (R inside P) |
  | `ne` | not `eq` |
  | `gt` | `re > pe` |
  | `lt` | `rs < ps` |
  | `ge` | `gt` or `eq` |
  | `le` | `lt` or `eq` |
  | `sa` | `rs >= pe` |
  | `eb` | `re <= ps` |

**`:missing=true|false`** is allowed on every parameter: `true` matches
resources where the element is absent, `false` where it is present. Any other
value is invalid. `:exact`/`:contains` are only allowed on string parameters.

**Controls**
- `_count=N` (non-negative integer): `Bundle.total` is the number of matches,
  `entry` holds the first N (after sorting).
- `_sort=a,-b`: sort keys in order, `-` = descending. Allowed keys are the
  string, token and date parameters of the resource type (including `_id`).
  Key value: the first element value (strings compared lower-cased, tokens by
  code, dates by the start of their range). Resources without a value sort
  **last in both directions**. Remaining ties: resource id ascending.
- `_format` and `_pretty` are accepted and ignored.

## Errors

Return an `OperationOutcome` with a single issue
`{ severity: 'error', code, diagnostics }` (exact texts, the harness compares them):

| Situation | code | diagnostics |
| --- | --- | --- |
| parameter not defined for the type (including other `_xxx` parameters) | `not-supported` | `Unknown search parameter "<name>" for <Type>` |
| modifier not allowed for the parameter | `invalid` | `Unsupported modifier ":<modifier>" on parameter "<name>"` |
| unparsable value (bad date, bad prefix, bad `:missing` value) | `invalid` | `Invalid value "<value>" for parameter "<name>"` |
| bad `_count` / unknown `_sort` key | `invalid` | `Invalid value "<value>" for parameter "_count"` / `"_sort"` (value = the offending item as written, e.g. `-colour`) |

## Acceptance criteria

- All semantics above, verified against the fixtures in `test/fixtures.ts`.
- Existing tests keep passing; `search()` never throws for client input.

## Constraints

- No dependencies; erasable TypeScript only (Node 24 type stripping).
- Keep the public exports of `src/index.ts` and the `Bundle` shape unchanged.
