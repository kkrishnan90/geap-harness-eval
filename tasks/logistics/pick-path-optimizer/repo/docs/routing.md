# Routing and batching notes (WMS-OPS wiki export)

* Travel model: S-shape/return hybrid on a parallel-aisle block with front and
  back cross-aisles; see `layout.rs`. Distances are symmetric.
* Construction heuristic: nearest neighbour from the depot (P&D point at the
  front of aisle 0). Improvement: best-improvement 2-opt until no improving
  move or `max_passes`. Because distances are symmetric, reversing
  `tour[i..=j]` only changes the two edges at the segment boundaries.
* Batching: seed-and-grow by anchor distance to the batch seed (see
  `batch.rs` doc comment for the exact rule and tie-breaks).
* Cost model: each `DistanceOracle::dist` call is a remote travel-time lookup
  in production. Budget per wave is tracked in Grafana
  (`pickplan_distance_lookups_total`).
