//! Picker routing for one batch: closed tour depot -> stops -> depot.

use crate::layout::LocId;
use crate::matrix::DistMatrix;
use crate::oracle::DistanceOracle;

#[derive(Clone, Copy, Debug)]
pub struct RouteParams {
    /// Maximum number of 2-opt improvement passes.
    pub max_passes: usize,
}

impl Default for RouteParams {
    fn default() -> Self {
        RouteParams { max_passes: 50 }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Route {
    /// Stops in visiting order, excluding the depot at start and end.
    pub stops: Vec<LocId>,
    /// Total length of depot -> stops -> depot in decimetres.
    pub length: u64,
}

/// Plans the walking route for a set of pick locations.
///
/// * Stops are the distinct values of `picks`, excluding the depot.
/// * Construction: nearest neighbour from the depot; ties go to the smaller `LocId`.
/// * Improvement: up to `max_passes` passes of best-improvement 2-opt on the closed tour
///   `[depot, s1, .., sn, depot]`: each pass evaluates reversing every segment
///   `tour[i..=j]` with `1 <= i < j <= n`, applies the move with the largest strictly
///   positive length reduction (ties: smallest `i`, then smallest `j`), and stops early
///   when no move improves the tour.
pub fn plan_route(oracle: &DistanceOracle, depot: LocId, picks: &[LocId], params: &RouteParams) -> Route {
    let mut stops: Vec<LocId> = picks.to_vec();
    stops.sort_unstable();
    stops.dedup();
    stops.retain(|&l| l != depot);
    let n = stops.len();
    if n == 0 {
        return Route { stops: Vec::new(), length: 0 };
    }

    // node 0 = depot, nodes 1..=n = stops in ascending LocId order; each pair looked up once
    let mut nodes = Vec::with_capacity(n + 1);
    nodes.push(depot);
    nodes.extend_from_slice(&stops);
    let m = DistMatrix::build(oracle, &nodes);

    // nearest-neighbour construction (ties: smaller LocId == smaller node index)
    let mut tour: Vec<usize> = Vec::with_capacity(n + 2);
    tour.push(0);
    let mut visited = vec![false; n + 1];
    visited[0] = true;
    let mut current = 0usize;
    for _ in 0..n {
        let mut best: Option<(u32, usize)> = None;
        for cand in 1..=n {
            if visited[cand] {
                continue;
            }
            let key = (m.get(current, cand), cand);
            if best.map_or(true, |b| key < b) {
                best = Some(key);
            }
        }
        let (_, next) = best.expect("unvisited stop");
        visited[next] = true;
        tour.push(next);
        current = next;
    }
    tour.push(0);

    // best-improvement 2-opt; with symmetric distances only the two boundary edges change
    for _ in 0..params.max_passes {
        let mut best: Option<(i64, usize, usize)> = None;
        for i in 1..n {
            for j in (i + 1)..=n {
                let (a, b, c, d) = (tour[i - 1], tour[i], tour[j], tour[j + 1]);
                let gain = m.get(a, b) as i64 + m.get(c, d) as i64 - m.get(a, c) as i64 - m.get(b, d) as i64;
                if gain > 0 && best.map_or(true, |(g, _, _)| gain > g) {
                    best = Some((gain, i, j));
                }
            }
        }
        match best {
            Some((_, i, j)) => tour[i..=j].reverse(),
            None => break,
        }
    }

    let length = tour.windows(2).map(|w| m.get(w[0], w[1]) as u64).sum();
    Route { stops: tour[1..=n].iter().map(|&k| nodes[k]).collect(), length }
}
