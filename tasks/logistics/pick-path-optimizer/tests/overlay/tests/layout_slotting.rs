use pickplan::slotting::{classify, VelocityClass};
use pickplan::{report, synth, Layout, Location, Order, OrderLine, Route};

#[test]
fn id_roundtrip_and_labels() {
    let l = synth::dc07_layout();
    for id in [0u32, 1, 163, l.location_count() - 1] {
        assert_eq!(l.id_of(l.location(id).unwrap()), Some(id));
    }
    assert_eq!(l.location(l.location_count()), None);
    let id = l.id_of(Location { aisle: 3, bay: 12, level: 0 }).unwrap();
    assert_eq!(l.label(id), "A03-B12-L1");
    assert_eq!(l.id_of(Location { aisle: 12, bay: 1, level: 0 }), None);
}

#[test]
fn abc_classes() {
    let mk = |id, skus: &[&str]| Order {
        id,
        lines: skus.iter().map(|s| OrderLine { sku: s.to_string(), qty: 1, loc: 1 }).collect(),
    };
    let mut orders = Vec::new();
    for i in 0..16 {
        orders.push(mk(i, &["FAST"]));
    }
    orders.push(mk(100, &["MID", "MID", "MID"]));
    orders.push(mk(101, &["SLOW"]));
    let c = classify(&orders);
    assert_eq!(c[0], ("FAST".to_string(), 16, VelocityClass::A));
    assert_eq!(c[1], ("MID".to_string(), 3, VelocityClass::B));
    assert_eq!(c[2], ("SLOW".to_string(), 1, VelocityClass::C));
}

#[test]
fn pick_list_lines() {
    let l = Layout::new(2, 10, 2, 30, 10);
    let a = l.id_of(Location { aisle: 1, bay: 4, level: 1 }).unwrap();
    let orders = vec![Order { id: 7, lines: vec![OrderLine { sku: "SKU-VERYLONGNAME".into(), qty: 2, loc: a }] }];
    let lines = report::pick_list(&l, &Route { stops: vec![a], length: 0 }, &orders);
    assert_eq!(lines, vec!["01 A01-B04-L2  SKU-VERYLONG x2   (7)".to_string()]);
}

#[test]
fn synth_is_deterministic() {
    let l = synth::dc07_layout();
    assert_eq!(synth::orders(&l, 42, 20, 5), synth::orders(&l, 42, 20, 5));
    assert_ne!(synth::picks(&l, 1, 10), synth::picks(&l, 2, 10));
}
