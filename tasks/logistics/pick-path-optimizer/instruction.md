# WMS-5521: Wave planning hammers the travel-time service (pickplan)

**Component:** `pickplan` crate · **Priority:** High · **Type:** Performance

## Context

Since DC-07 moved to the remote WMS travel-time service, every
`DistanceOracle::dist` call is a network round trip (~0.3 ms). Planning the
morning wave (~3,000 orders) now takes over 40 minutes and the service team
is throttling us. `oracle.lookups()` (exported as
`pickplan_distance_lookups_total`) shows `pickplan` issues orders of magnitude
more lookups than it needs: the routing code re-sorts and re-measures
candidates on every step, the 2-opt loop re-walks the whole tour for every
candidate move, batching re-measures the same seed-to-order distances for
every order it adds, and `plan_wave` walks every route again as a sanity
check.

The planning **results are correct and must not change** — the downstream
labour-standards model is calibrated on them. This is purely a lookup-count
optimisation.

## Requirements

1. Output must be identical to today's for every input: same batches (same
   order ids, in the same order, same units), same route stop order and
   length, same tie-breaking. The algorithms and tie-breaks are documented
   on `form_batches` (`src/batch.rs`) and `plan_route` (`src/route.rs`);
   README "Distance lookups" describes the distance properties you may rely
   on (symmetric, integer, `dist(a, a) == 0`).
2. Every distance must still come from `DistanceOracle::dist` (no computing
   distances from coordinates, no caches that outlive a single call of the
   public function). `src/oracle.rs` and `src/layout.rs` must not be modified
   (CI replaces them with the canonical copies).
3. Lookup budgets, counted with `oracle.lookups()`, in debug and release builds:
   - `plan_route` with `n` distinct stops (distinct values of `picks`, depot
     excluded): at most `(n + 1) * (n + 2) / 2` lookups, regardless of
     `max_passes`.
   - `form_batches`: when a batch is opened, `r` orders (with lines) are
     still unbatched including its seed; the call may use at most the sum
     over all batches of `r - 1` lookups.
   - `plan_wave`: at most the `form_batches` budget plus the `plan_route`
     budget of each batch (i.e. no lookups of its own).

## Constraints

- Keep all public types and function signatures (the WMS adapter links
  against them). Std only, `cargo test --offline`.
- Existing tests must keep passing.
