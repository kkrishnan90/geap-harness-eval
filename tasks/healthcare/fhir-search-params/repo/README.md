# @clinic/fhir-lite

A small in-memory FHIR R4 repository (Patient, Observation) with the FHIR
REST search semantics we need for:

* the **kiosk offline cache** (patients check in while the EHR link is down),
* the **integration engine test harness**, which replays recorded FHIR
  queries from the EHR vendor against fixtures.

Only the subset of FHIR we use is implemented; see `src/search/registry.ts`
for the supported search parameters.

## Layout

| Path | Purpose |
| --- | --- |
| `src/resources.ts` | TypeScript shapes of the FHIR resources we store |
| `src/store.ts` | `InMemoryStore`: create/read/update/delete, insertion-ordered |
| `src/search/registry.ts` | Search parameter definitions per resource type (name, type, element extractor) |
| `src/search/parse.ts` | Query-string parsing |
| `src/search/execute.ts` | `search(store, resourceType, query)` -> searchset `Bundle` or `OperationOutcome` |
| `src/datetime.ts` | FHIR date/dateTime helpers |
| `src/outcome.ts`, `src/bundle.ts` | Builders for `OperationOutcome` and `Bundle` |
| `src/validate.ts` | Structural validation on create/update |
| `src/format.ts` | Display helpers (human names) for the kiosk UI |

## Conventions

* Node 24, TypeScript run directly via type stripping (erasable syntax only:
  no `enum`, `namespace`, parameter properties). No dependencies.
* Search never throws for bad client input: it returns an `OperationOutcome`.
* Without `_sort`, search results are in store insertion order.
* Synthetic test data only. Never commit real patient data.
* Tests: `npm test` (`node --test test/*.test.ts`).

## References

* FHIR R4 search: https://hl7.org/fhir/R4/search.html
