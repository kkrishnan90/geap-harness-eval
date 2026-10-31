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

        // one lookup per remaining order and batch: distance of its anchor to the seed's
        let mut cands: Vec<(u32, u32, usize)> = pending
            .iter()
            .enumerate()
            .map(|(idx, o)| (oracle.dist(seed_anchor, o.anchor().unwrap()), o.id, idx))
            .collect();
        cands.sort_unstable();
        let mut taken = vec![false; pending.len()];
        // nearest first; an order that does not fit now cannot fit later (units only grow)
        for &(_, _, idx) in &cands {
            if batch.order_ids.len() >= params.max_orders {
                break;
            }
            let o = pending[idx];
            if batch.units + o.units() <= params.max_units {
                batch.units += o.units();
                batch.order_ids.push(o.id);
                taken[idx] = true;
            }
        }
        let mut k = 0;
        pending.retain(|_| {
            let keep = !taken[k];
            k += 1;
            keep
        });
        batches.push(batch);
    }
    batches
}
