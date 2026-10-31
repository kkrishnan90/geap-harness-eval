# pickplan

Wave planner used by the WMS at distribution centre DC-07. For every pick
wave it groups customer orders into picker batches (one trolley each) and
computes the walking route for each batch through the aisles.

## Modules

| Module | Purpose |
| --- | --- |
| `layout` | Warehouse geometry: parallel aisles, front/back cross-aisles, `LocId` encoding |
| `oracle` | `DistanceOracle`: **the only way to get travel distances**; counts every lookup |
| `order` | Orders, order lines, anchor locations |
| `batch` | Order batching (`form_batches`) |
| `route` | Picker routing: nearest-neighbour construction + best-improvement 2-opt (`plan_route`) |
| `wave` | `plan_wave` = batching + one route per batch |
| `slotting` | ABC velocity classification for re-slotting proposals (nightly job) |
| `report` | Pick-list rendering for the handheld terminals |
| `synth` | Deterministic synthetic layouts/orders (xorshift) for tests and the simulator |

`src/bin/sim.rs` plans a synthetic wave and prints the KPIs.

## Distance lookups

In production the oracle is backed by the WMS travel-time service (a remote
call per lookup, ~0.3 ms), so the number of `DistanceOracle::dist` calls is
the cost metric we track (`oracle.lookups()`). Code must never compute
distances itself from coordinates. Distances are symmetric integers
(decimetres) and `dist(a, a) == 0`.

## Conventions

* Rust 2021, std only, `cargo test --offline`.
* Planning output must be deterministic: every tie is broken explicitly
  (documented on each function).
* Public functions and types keep their signatures (the WMS adapter crate
  links against them).
