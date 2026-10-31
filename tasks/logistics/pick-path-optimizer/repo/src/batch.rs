//! Order batching: groups the wave's orders into picker batches (one trolley each).

use crate::oracle::DistanceOracle;
use crate::order::Order;

#[derive(Clone, Copy, Debug)]
pub struct BatchParams {
    /// Maximum orders per trolley (number of totes).
    pub max_orders: usize,
    /// Maximum units per trolley.
    pub max_units: u32,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Batch {
    /// Order ids in the order they were added to the batch (seed first).
    pub order_ids: Vec<u32>,
    pub units: u32,
}

/// Seed-and-grow batching.
///
/// Orders without lines are ignored. While unbatched orders remain:
/// 1. the unbatched order with the smallest id becomes the batch seed (always accepted,
///    even if it alone exceeds `max_units`);
/// 2. repeatedly add the unbatched order that fits (`order_ids.len() < max_orders` and
///    `units + order.units() <= max_units`) whose anchor is closest to the **seed's**
///    anchor (`oracle.dist(seed_anchor, anchor)`); ties go to the smaller order id;
/// 3. the batch is closed when no remaining order fits.
pub fn form_batches(oracle: &DistanceOracle, orders: &[Order], params: &BatchParams) -> Vec<Batch> {
    let mut pending: Vec<&Order> = orders.iter().filter(|o| o.anchor().is_some()).collect();
    pending.sort_by_key(|o| o.id);

    let mut batches = Vec::new();
    while !pending.is_empty() {
        let seed = pending.remove(0);
        let seed_anchor = seed.anchor().unwrap();
        let mut batch = Batch { order_ids: vec![seed.id], units: seed.units() };

        loop {
            if batch.order_ids.len() >= params.max_orders {
                break;
            }
            let mut best: Option<(u32, u32, usize)> = None; // (dist, id, index)
            for (idx, cand) in pending.iter().enumerate() {
                if batch.units + cand.units() > params.max_units {
                    continue;
                }
                let d = oracle.dist(seed_anchor, cand.anchor().unwrap());
                let key = (d, cand.id, idx);
                if best.map_or(true, |b| (key.0, key.1) < (b.0, b.1)) {
                    best = Some(key);
                }
            }
            match best {
                Some((_, _, idx)) => {
                    let o = pending.remove(idx);
                    batch.units += o.units();
                    batch.order_ids.push(o.id);
                }
                None => break,
            }
        }
        batches.push(batch);
    }
    batches
}
