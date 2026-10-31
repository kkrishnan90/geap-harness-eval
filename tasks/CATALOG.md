# Task catalog (36 tasks: 12 MVP ★ + 24 extended)

Package format and verifier contract: `docs/CONTRACTS.md` §1. Validate with
`uv run python scripts/validate_tasks.py [task_id ...]`.

| id | tier | industry | sdlc_type | language | summary |
| --- | --- | --- | --- | --- | --- |
| ★ banking/iban-checksum-bug | simple | banking | bug-fix | python | IBAN validation rejects lowercase/spaced input and accepts wrong-length or unknown-country IBANs; fix normalisation, exact registry length and mod-97 order. |
| ★ banking/pain001-batch-booking | medium | banking | feature | java | Parse the pain.001 `BtchBookg` flag (JDK DOM only), apply defaulting for urgent/instant payments, add batch validation rules and one-debit-per-batch booking. |
| ★ banking/ledger-fx-rounding | complex | banking | bug-fix | java | Multi-currency double-entry ledger drifts at month-end FX revaluation; move to BigDecimal with banker's rounding and keep every entry balanced (debits == credits). |
| ★ telecom/e164-normalizer | simple | telecom | bug-fix | typescript | E.164 normaliser mishandles international dialling prefixes, NANP `+1`, the `(0)` trunk marker and Italian leading zeros (Node 24 type stripping, `node --test`). |
| ★ telecom/cdr-tiered-tariff | medium | telecom | feature | go | CDR rating: billing increments, peak/off-peak bands in the plan's time zone with holidays, monthly usage tiers split across boundaries, JSON tariff loading. |
| ★ retail/promo-expiry-timezone | simple | retail | bug-fix | python | Promotions expire an hour or a day early/late across store time zones and DST; fix validity windows, inclusive end-of-day and local-date day counts (zoneinfo). |
| ★ retail/inventory-reservation-race | complex | retail | bug-fix | java | Concurrent checkout oversells stock and double-reserves/releases; make reserve/release/commit/restock atomic per SKU and idempotent without a global lock. |
| ★ oem-devices/can-signed-signal | simple | oem-devices | bug-fix | c | CAN decoder extracts signed and Motorola (big-endian) signals wrongly; fix sign extension up to 64 bits and DBC big-endian bit walking. |
| ★ oem-devices/ota-manifest-verify | medium | oem-devices | feature | rust | OTA manifest format 2: numeric version ordering, anti-rollback with security-version floor, per-chunk SHA-256 digest verification (std only, vendored SHA-256). |
| ★ logistics/eta-dst-bug | simple | logistics | bug-fix | go | Line-haul ETAs are off by one hour across DST changes because drive time is added on the local wall clock; compute in elapsed time and rebuild dock windows correctly. |
| ★ energy/telemetry-window-agg | complex | energy | feature | java | Grid telemetry pipeline: event-time tumbling/sliding windows with watermark and allowed lateness, late-event side output, and a bounded ingest buffer with overflow policies. |
| ★ healthcare/phi-redaction | complex | healthcare | feature | python | Log sidecar only strips SSNs; add format-aware PHI redaction for HL7v2, JSON, key=value and free text, without over-redacting, plus an HMAC-keyed audit trail. |
| banking/statement-download-traversal | simple | banking | security | go | Statement PDF download joins user filenames onto the archive dir; block `..`, encoded traversal, absolute paths, NUL and symlink escapes while nested names keep working. |
| banking/statement-search-sqli | medium | banking | security | python | Transaction search builds SQL with f-strings; switch to bound parameters, allowlisted ORDER BY/direction and escaped LIKE wildcards with search behaviour unchanged (stdlib sqlite3). |
| telecom/slice-quota-ratelimiter | medium | telecom | feature | go | Hierarchical per-slice / per-subscriber token buckets for the 5G PCF: injected clock, integer refill with carried remainder, burst, exact RetryAfter, concurrency-safe. |
| telecom/number-port-refactor | medium | telecom | refactor | typescript | Three drifted copies of number-porting validation (mobile, fixed, bulk) consolidated into one injectable rules module with the specified intended behaviour. |
| telecom/sip-parser-hardening | complex | telecom | security | rust | SBC SIP parser panics or over-allocates on hostile input; add limits and typed errors (Content-Length, header count/length, folding, CSeq overflow, non-UTF-8) and never panic (fixed-seed fuzz). |
| retail/deploy-manifest-policy | simple | retail | ci-repair | json, python | IaC: checkout-service Deployment/Service/HPA JSON manifests fail the stdlib policy validator in CI; fix the manifests (limits, probes, pinned images, replicas, selectors) and one validator unit bug. |
| retail/cart-stackable-promos | medium | retail | feature | typescript | Cart pricing gains stackable promotions: BOGO/percent/fixed ordering, priorities, exclusivity groups, per-line caps, cent rounding and a rejection breakdown. |
| retail/loyalty-javatime-upgrade | medium | retail | upgrade | java | Migrate the loyalty points API from Date/Calendar/SimpleDateFormat to java.time, with member-zone month-end expiry, leap-day anniversaries and thread-safe formatting. |
| oem-devices/firmware-ci-repair | simple | oem-devices | ci-repair | c, make | `make ci` is broken (include-path ordering, a real -Wsign-compare bug under -Werror, tests that never run or always pass, no header dependency tracking). |
| oem-devices/spsc-ring-buffer-fix | medium | oem-devices | bug-fix | c | C11 lock-free SPSC sensor ring buffer: uint32 wraparound, full/empty ambiguity, wrapped batch reads and memory ordering. |
| oem-devices/ble-gatt-state-machine | complex | oem-devices | refactor | c | Nested-switch BLE connection/pairing/bonding manager refactored into a table-driven FSM with the specified API; golden event traces must replay identically. |
| logistics/carrier-rate-tests | simple | logistics | test-authoring | python | Write unit tests for parcel rating (dimensional weight, 0.5 kg rounding, limits, surcharges); graded by passing on the reference and killing hidden mutants. |
| logistics/route-batch-csv-ingest | medium | logistics | ci-repair | python | Route batch CI silently skips tests (stdlib `csv` shadowing, bad discovery, cwd/hash-order dependence) and hides real ingest bugs (BOM, `;` delimiter, quoted newlines). |
| logistics/pick-path-optimizer | complex | logistics | performance | rust | Pick-wave planner is correct but O(n^3) in distance lookups; meet counted lookup budgets with byte-identical plans (instrumented oracle, no wall clock). |
| energy/tou-billing | simple | energy | bug-fix | python | Time-of-use billing misassigns 15-min intervals on DST days and wrap-past-midnight bands, and rounds money in float; fix bands, daily charges and half-up line rounding. |
| energy/smart-meter-dedupe | medium | energy | bug-fix | sql | sqlite3 CLI scripts: dedupe must prefer actual over estimated then latest received, and the daily rollup must stop double counting feeder moves and NULL counters. |
| energy/meter-validation-tests | medium | energy | test-authoring | go | Write Go tests pinning down MDM VEE validation/estimation rules; graded by passing on the reference and killing hidden single-rule mutants. |
| healthcare/hl7-escape-handling | simple | healthcare | bug-fix | python | HL7 v2 encoder/decoder: escaped escapes, sequential-replace decoding, custom MSH-1/MSH-2 delimiters, `\Xhh\` hex and CR/LF in data. |
| healthcare/fhir-search-params | medium | healthcare | feature | typescript | In-memory FHIR R4 search: `:exact`/`:contains`/`:missing`, date prefixes with precision ranges, token system/code, OR/AND, `_sort`, `_count`, OperationOutcome errors. |
| healthcare/patient-matching-perf | medium | healthcare | performance | python | MPI record linkage scores all pairs; add lossless blocking so results are identical and counted comparisons stay within budget. |
| insurance/premium-rounding | simple | insurance | bug-fix | java | Premium calculation rounds after every factor with HALF_UP and taxes the unrounded net; instalments do not sum to the annual premium. |
| insurance/claims-fraud-rules-tests | medium | insurance | test-authoring | java | Write boundary tests for a six-rule claims fraud screening engine; graded by passing on the reference and killing hidden mutant engines. |
| insurance/policy-import-deserialization | medium | insurance | security | java | Legacy policy batch upload deserializes untrusted bytes; add a strict per-stream ObjectInputFilter allowlist with depth/array limits so gadget classes never run `readObject`. |
| insurance/fixed-width-rating-port | complex | insurance | upgrade | python | Finish the COBOL PRMRATE premium-rating port: overpunch signs, implied decimals, ROUNDED semantics, record routing and trailer totals, byte-exact against golden files. |

### Coverage

| industry | simple | medium | complex |
| --- | --- | --- | --- |
| banking | 2 | 2 | 1 |
| telecom | 1 | 3 | 1 |
| retail | 2 | 2 | 1 |
| oem-devices | 2 | 2 | 1 |
| logistics | 2 | 1 | 1 |
| energy | 1 | 2 | 1 |
| healthcare | 1 | 2 | 1 |
| insurance | 1 | 2 | 1 |

SDLC types: bug-fix 12, feature 8, security 4, test-authoring 3, ci-repair 3 (incl. the IaC task
retail/deploy-manifest-policy), refactor 2, upgrade 2, performance 2.

Test-authoring tasks are graded by mutation: the agent's tests must pass on the pristine reference
implementation (`agent_tests_pass_on_reference`), and each hidden mutant (`mutant::<name>`) counts as
killed only if the suite then fails on it. Performance tasks are graded by instrumented operation
counters (pristine-overlaid), never wall-clock time.

## Conventions shared by all tasks

- `tests/lib.sh` is a verbatim copy of `tasks/_shared/lib.sh` (the validator checks this). It writes
  the results JSON on every exit path; tests that never report (compile error, crash, timeout) count as failed.
- `tests/expected_f2p.txt` / `tests/expected_p2p.txt` list the test ids. Hidden regression-guard
  tests that already pass on the seed (e.g. "must not over-redact") are counted as P2P.
- `tests/overlay/` is copied over the workdir before running, so pristine copies of the visible
  tests and the test harness replace any agent edits.
- Feature tasks keep F2P tests in their own compilation unit (Java class, Go package, Rust test
  target), so a seed that lacks the new API fails only the F2P tests.
