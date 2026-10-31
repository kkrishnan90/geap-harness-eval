//! Picker routing for one batch: closed tour depot -> stops -> depot.

use crate::layout::LocId;
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

fn tour_length(oracle: &DistanceOracle, tour: &[LocId]) -> u64 {
    tour.windows(2).map(|w| oracle.dist(w[0], w[1]) as u64).sum()
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
    let mut unvisited: Vec<LocId> = picks.to_vec();
    unvisited.sort_unstable();
    unvisited.dedup();
    unvisited.retain(|&l| l != depot);
    let n = unvisited.len();
    if n == 0 {
        return Route { stops: Vec::new(), length: 0 };
    }

    // nearest-neighbour construction
    let mut tour = Vec::with_capacity(n + 2);
    tour.push(depot);
    let mut current = depot;
    while !unvisited.is_empty() {
        unvisited.sort_by(|a, b| {
            oracle.dist(current, *a).cmp(&oracle.dist(current, *b)).then(a.cmp(b))
        });
        current = unvisited.remove(0);
        tour.push(current);
    }
    tour.push(depot);

    // best-improvement 2-opt
    for _ in 0..params.max_passes {
        let base = tour_length(oracle, &tour) as i64;
        let mut best: Option<(i64, usize, usize)> = None;
        for i in 1..n {
            for j in (i + 1)..=n {
                let mut cand = tour.clone();
                cand[i..=j].reverse();
                let gain = base - tour_length(oracle, &cand) as i64;
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

    let length = tour_length(oracle, &tour);
    Route { stops: tour[1..=n].to_vec(), length }
}
