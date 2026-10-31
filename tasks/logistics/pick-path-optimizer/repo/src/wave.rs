//! Wave planning: batching + one route per batch.

use crate::batch::{form_batches, Batch, BatchParams};
use crate::oracle::DistanceOracle;
use crate::order::Order;
use crate::route::{plan_route, Route, RouteParams};

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct WavePlan {
    pub batches: Vec<Batch>,
    /// `routes[k]` is the route of `batches[k]`.
    pub routes: Vec<Route>,
}

impl WavePlan {
    pub fn total_length(&self) -> u64 {
        self.routes.iter().map(|r| r.length).sum()
    }
}

pub fn plan_wave(oracle: &DistanceOracle, orders: &[Order], batch: &BatchParams, route: &RouteParams) -> WavePlan {
    let depot = oracle.layout().depot();
    let batches = form_batches(oracle, orders, batch);
    let mut routes = Vec::with_capacity(batches.len());
    for b in &batches {
        let mut picks = Vec::new();
        for id in &b.order_ids {
            let o = orders.iter().find(|o| o.id == *id).expect("batched order exists");
            picks.extend(o.locations());
        }
        let r = plan_route(oracle, depot, &picks, route);
        // sanity check: the route length must match a fresh walk of the tour
        debug_assert_eq!(r.length, walk_length(oracle, depot, &r.stops));
        routes.push(r);
    }
    WavePlan { batches, routes }
}

fn walk_length(oracle: &DistanceOracle, depot: u32, stops: &[u32]) -> u64 {
    let mut prev = depot;
    let mut total = 0u64;
    for &s in stops.iter().chain(std::iter::once(&depot)) {
        total += oracle.dist(prev, s) as u64;
        prev = s;
    }
    total
}
