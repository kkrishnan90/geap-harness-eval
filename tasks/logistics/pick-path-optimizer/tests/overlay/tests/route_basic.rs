use pickplan::{plan_route, DistanceOracle, Layout, Location, RouteParams};

fn layout() -> Layout {
    Layout::new(4, 10, 2, 30, 10)
}

fn id(l: &Layout, aisle: u16, bay: u16, level: u8) -> u32 {
    l.id_of(Location { aisle, bay, level }).unwrap()
}

#[test]
fn distances_are_symmetric_and_use_cross_aisles() {
    let l = layout();
    let o = DistanceOracle::new(&l);
    let a = id(&l, 0, 2, 0);
    let b = id(&l, 3, 9, 1);
    assert_eq!(o.dist(a, b), o.dist(b, a));
    // same aisle: straight walk
    assert_eq!(o.dist(id(&l, 1, 2, 0), id(&l, 1, 7, 1)), 50);
    // different aisles near the back: via back cross-aisle (y_back = 110)
    assert_eq!(o.dist(id(&l, 0, 9, 0), id(&l, 2, 10, 0)), 60 + 20 + 10);
    assert_eq!(o.dist(a, a), 0);
    assert_eq!(o.lookups(), 5);
}

#[test]
fn empty_and_depot_only() {
    let l = layout();
    let o = DistanceOracle::new(&l);
    let r = plan_route(&o, l.depot(), &[], &RouteParams::default());
    assert!(r.stops.is_empty());
    assert_eq!(r.length, 0);
    let r = plan_route(&o, l.depot(), &[l.depot(), l.depot()], &RouteParams::default());
    assert!(r.stops.is_empty());
}

#[test]
fn single_aisle_out_and_back() {
    let l = layout();
    let o = DistanceOracle::new(&l);
    let picks = [id(&l, 0, 5, 0), id(&l, 0, 2, 1), id(&l, 0, 8, 0), id(&l, 0, 5, 0)];
    let r = plan_route(&o, l.depot(), &picks, &RouteParams::default());
    assert_eq!(r.stops, vec![id(&l, 0, 2, 1), id(&l, 0, 5, 0), id(&l, 0, 8, 0)]);
    assert_eq!(r.length, 160);
}

#[test]
fn stops_are_a_permutation_and_length_matches() {
    let l = layout();
    let o = DistanceOracle::new(&l);
    let picks: Vec<u32> = vec![id(&l, 3, 1, 0), id(&l, 1, 9, 1), id(&l, 2, 4, 0), id(&l, 0, 7, 1), id(&l, 3, 8, 0)];
    let r = plan_route(&o, l.depot(), &picks, &RouteParams::default());
    let mut sorted = r.stops.clone();
    sorted.sort();
    let mut expect = picks.clone();
    expect.sort();
    assert_eq!(sorted, expect);
    let mut walk = 0u64;
    let mut prev = l.depot();
    for &s in r.stops.iter().chain(std::iter::once(&l.depot())) {
        walk += o.dist(prev, s) as u64;
        prev = s;
    }
    assert_eq!(walk, r.length);
}

#[test]
fn two_opt_never_worse_than_construction() {
    let l = layout();
    let o = DistanceOracle::new(&l);
    let picks: Vec<u32> = (0..4).flat_map(|a| [id(&l, a, 1, 0), id(&l, a, 10, 0)]).collect();
    let nn = plan_route(&o, l.depot(), &picks, &RouteParams { max_passes: 0 });
    let opt = plan_route(&o, l.depot(), &picks, &RouteParams::default());
    assert!(opt.length <= nn.length);
}
