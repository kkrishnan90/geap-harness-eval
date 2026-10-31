//! Verifier-side reference implementation (straightforward, unoptimised) and budget helpers.
#![allow(dead_code)]

use pickplan::{Batch, BatchParams, DistanceOracle, LocId, Order, Route, RouteParams};

fn tour_length(o: &DistanceOracle, tour: &[LocId]) -> u64 {
    tour.windows(2).map(|w| o.dist(w[0], w[1]) as u64).sum()
}

pub fn ref_route(o: &DistanceOracle, depot: LocId, picks: &[LocId], p: &RouteParams) -> Route {
    let mut un: Vec<LocId> = picks.to_vec();
    un.sort_unstable();
    un.dedup();
    un.retain(|&l| l != depot);
    let n = un.len();
    if n == 0 {
        return Route { stops: vec![], length: 0 };
    }
    let mut tour = vec![depot];
    let mut cur = depot;
    while !un.is_empty() {
        let mut best = 0usize;
        let mut bd = o.dist(cur, un[0]);
        for k in 1..un.len() {
            let d = o.dist(cur, un[k]);
            if d < bd {
                bd = d;
                best = k;
            }
        }
        cur = un.remove(best);
        tour.push(cur);
    }
    tour.push(depot);
    for _ in 0..p.max_passes {
        let base = tour_length(o, &tour) as i64;
        let mut best: Option<(i64, usize, usize)> = None;
        for i in 1..n {
            for j in (i + 1)..=n {
                let mut c = tour.clone();
                c[i..=j].reverse();
                let g = base - tour_length(o, &c) as i64;
                if g > 0 && best.map_or(true, |(bg, _, _)| g > bg) {
                    best = Some((g, i, j));
                }
            }
        }
        match best {
            Some((_, i, j)) => tour[i..=j].reverse(),
            None => break,
        }
    }
    let length = tour_length(o, &tour);
    Route { stops: tour[1..=n].to_vec(), length }
}

pub fn ref_batches(o: &DistanceOracle, orders: &[Order], p: &BatchParams) -> Vec<Batch> {
    let mut pending: Vec<&Order> = orders.iter().filter(|x| !x.lines.is_empty()).collect();
    pending.sort_by_key(|x| x.id);
    let mut out = Vec::new();
    while !pending.is_empty() {
        let seed = pending.remove(0);
        let sa = seed.anchor().unwrap();
        let mut b = Batch { order_ids: vec![seed.id], units: seed.units() };
        while b.order_ids.len() < p.max_orders {
            let mut best: Option<(u32, u32, usize)> = None;
            for (k, c) in pending.iter().enumerate() {
                if b.units + c.units() > p.max_units {
                    continue;
                }
                let key = (o.dist(sa, c.anchor().unwrap()), c.id, k);
                if best.map_or(true, |x| (key.0, key.1) < (x.0, x.1)) {
                    best = Some(key);
                }
            }
            match best {
                Some((_, _, k)) => {
                    let c = pending.remove(k);
                    b.units += c.units();
                    b.order_ids.push(c.id);
                }
                None => break,
            }
        }
        out.push(b);
    }
    out
}

/// Distinct stops of a pick list (excluding the depot).
pub fn distinct_stops(depot: LocId, picks: &[LocId]) -> u64 {
    let mut v = picks.to_vec();
    v.sort_unstable();
    v.dedup();
    v.retain(|&l| l != depot);
    v.len() as u64
}

/// Route budget: (n + 1)(n + 2) / 2 lookups for n distinct stops.
pub fn route_budget(n: u64) -> u64 {
    (n + 1) * (n + 2) / 2
}

/// Batching budget: sum over batches of (orders still unbatched when the batch is opened) - 1.
pub fn batch_budget(orders: &[Order], batches: &[Batch]) -> u64 {
    let mut remaining = orders.iter().filter(|o| !o.lines.is_empty()).count() as u64;
    let mut total = 0;
    for b in batches {
        total += remaining - 1;
        remaining -= b.order_ids.len() as u64;
    }
    total
}

pub fn batch_picks(orders: &[Order], b: &Batch) -> Vec<LocId> {
    let mut picks = Vec::new();
    for id in &b.order_ids {
        picks.extend(orders.iter().find(|o| o.id == *id).unwrap().locations());
    }
    picks
}
