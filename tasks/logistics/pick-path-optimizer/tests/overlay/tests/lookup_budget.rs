mod common;

use common::*;
use pickplan::{form_batches, plan_route, plan_wave, synth, BatchParams, DistanceOracle, Layout, RouteParams};

fn check_route(layout: &Layout, seed: u64, n_picks: u32, passes: usize) {
    let picks = synth::picks(layout, seed, n_picks);
    let p = RouteParams { max_passes: passes };
    let reference = ref_route(&DistanceOracle::new(layout), layout.depot(), &picks, &p);
    let o = DistanceOracle::new(layout);
    let got = plan_route(&o, layout.depot(), &picks, &p);
    assert_eq!(got, reference, "route differs from reference (seed {seed}, {n_picks} picks)");
    let n = distinct_stops(layout.depot(), &picks);
    let budget = route_budget(n);
    assert!(o.lookups() <= budget, "plan_route used {} lookups for {} stops, budget {}", o.lookups(), n, budget);
}

#[test]
fn route_budget_small_batch() {
    let l = synth::dc07_layout();
    for seed in 1..=6 {
        check_route(&l, seed, 12, 50);
    }
}

#[test]
fn route_budget_full_trolley() {
    let l = synth::dc07_layout();
    check_route(&l, 77, 45, 50);
    check_route(&l, 78, 60, 50);
}

#[test]
fn route_budget_large_pick_list() {
    let l = synth::dc07_layout();
    check_route(&l, 2024, 110, 50);
}

#[test]
fn route_budget_many_duplicates() {
    let l = Layout::new(3, 8, 1, 30, 13);
    check_route(&l, 5, 200, 50);
}

#[test]
fn route_budget_construction_only() {
    let l = synth::dc07_layout();
    check_route(&l, 9, 40, 0);
}

#[test]
fn batch_budget_wave() {
    let l = synth::dc07_layout();
    let orders = synth::orders(&l, 31, 300, 5);
    let p = BatchParams { max_orders: 8, max_units: 40 };
    let reference = ref_batches(&DistanceOracle::new(&l), &orders, &p);
    let o = DistanceOracle::new(&l);
    let got = form_batches(&o, &orders, &p);
    assert_eq!(got, reference);
    let budget = batch_budget(&orders, &got);
    assert!(o.lookups() <= budget, "form_batches used {} lookups, budget {}", o.lookups(), budget);
}

#[test]
fn batch_budget_unit_bound() {
    let l = synth::dc07_layout();
    let orders = synth::orders(&l, 32, 150, 3);
    let p = BatchParams { max_orders: 12, max_units: 30 };
    let reference = ref_batches(&DistanceOracle::new(&l), &orders, &p);
    let o = DistanceOracle::new(&l);
    let got = form_batches(&o, &orders, &p);
    assert_eq!(got, reference);
    let budget = batch_budget(&orders, &got);
    assert!(o.lookups() <= budget, "form_batches used {} lookups, budget {}", o.lookups(), budget);
}

#[test]
fn wave_budget_is_sum_of_parts() {
    let l = synth::dc07_layout();
    let orders = synth::orders(&l, 33, 120, 5);
    let bp = BatchParams { max_orders: 8, max_units: 40 };
    let rp = RouteParams::default();
    let ro = DistanceOracle::new(&l);
    let ref_b = ref_batches(&ro, &orders, &bp);
    let mut budget = batch_budget(&orders, &ref_b);
    let mut ref_total = 0;
    for b in &ref_b {
        let picks = batch_picks(&orders, b);
        budget += route_budget(distinct_stops(l.depot(), &picks));
        ref_total += ref_route(&ro, l.depot(), &picks, &rp).length;
    }
    let o = DistanceOracle::new(&l);
    let plan = plan_wave(&o, &orders, &bp, &rp);
    assert_eq!(plan.batches, ref_b);
    assert_eq!(plan.total_length(), ref_total);
    assert!(o.lookups() <= budget, "plan_wave used {} lookups, budget {}", o.lookups(), budget);
}
