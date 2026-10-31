//! Plans a synthetic DC-07 wave and prints KPIs: `cargo run --bin sim -- [orders] [seed]`.

use pickplan::synth;
use pickplan::{plan_wave, BatchParams, DistanceOracle, RouteParams};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let n: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(200);
    let seed: u64 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(7);
    let layout = synth::dc07_layout();
    let orders = synth::orders(&layout, seed, n, 5);
    let oracle = DistanceOracle::new(&layout);
    let plan = plan_wave(&oracle, &orders, &BatchParams { max_orders: 8, max_units: 40 }, &RouteParams::default());
    println!("orders={} batches={} walk_m={:.1} lookups={}", n, plan.batches.len(),
             plan.total_length() as f64 / 10.0, oracle.lookups());
}
