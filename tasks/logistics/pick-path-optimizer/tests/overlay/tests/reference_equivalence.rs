//! Output must stay identical to the documented algorithm (regression guard).
mod common;

use common::*;
use pickplan::{form_batches, plan_route, plan_wave, report, synth, BatchParams, DistanceOracle, Layout, RouteParams};

#[test]
fn routes_match_reference_on_fixed_seeds() {
    let layouts = [synth::dc07_layout(), Layout::new(5, 15, 2, 25, 10), Layout::new(1, 30, 3, 30, 12)];
    for (li, l) in layouts.iter().enumerate() {
        for seed in 0..12u64 {
            let n = 1 + (seed as u32 * 7) % 36;
            let picks = synth::picks(l, seed * 13 + li as u64, n);
            for passes in [0usize, 1, 50] {
                let p = RouteParams { max_passes: passes };
                let want = ref_route(&DistanceOracle::new(l), l.depot(), &picks, &p);
                let got = plan_route(&DistanceOracle::new(l), l.depot(), &picks, &p);
                assert_eq!(got, want, "layout {li} seed {seed} passes {passes}");
            }
        }
    }
}

#[test]
fn ties_resolved_by_location_id() {
    // symmetric grid: many equal distances
    let l = Layout::new(4, 4, 1, 10, 10);
    let all: Vec<u32> = (1..l.location_count()).collect();
    let p = RouteParams::default();
    let want = ref_route(&DistanceOracle::new(&l), l.depot(), &all, &p);
    let got = plan_route(&DistanceOracle::new(&l), l.depot(), &all, &p);
    assert_eq!(got, want);
}

#[test]
fn batches_match_reference_on_fixed_seeds() {
    let l = synth::dc07_layout();
    for seed in 0..8u64 {
        let orders = synth::orders(&l, 500 + seed, 40 + seed as u32 * 9, 6);
        for p in [BatchParams { max_orders: 1, max_units: 100 }, BatchParams { max_orders: 6, max_units: 20 },
                  BatchParams { max_orders: 50, max_units: 1000 }] {
            let want = ref_batches(&DistanceOracle::new(&l), &orders, &p);
            let got = form_batches(&DistanceOracle::new(&l), &orders, &p);
            assert_eq!(got, want, "seed {seed}");
        }
    }
}

#[test]
fn wave_pick_lists_unchanged() {
    let l = synth::dc07_layout();
    let orders = synth::orders(&l, 99, 30, 4);
    let bp = BatchParams { max_orders: 5, max_units: 30 };
    let rp = RouteParams::default();
    let plan = plan_wave(&DistanceOracle::new(&l), &orders, &bp, &rp);
    let ro = DistanceOracle::new(&l);
    let ref_b = ref_batches(&ro, &orders, &bp);
    assert_eq!(plan.batches, ref_b);
    for (b, r) in ref_b.iter().zip(&plan.routes) {
        let want = ref_route(&ro, l.depot(), &batch_picks(&orders, b), &rp);
        assert_eq!(*r, want);
        let members: Vec<_> = orders.iter().filter(|o| b.order_ids.contains(&o.id)).cloned().collect();
        assert_eq!(report::pick_list(&l, r, &members), report::pick_list(&l, &want, &members));
    }
}
