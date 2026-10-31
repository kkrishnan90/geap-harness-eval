use pickplan::{form_batches, BatchParams, DistanceOracle, Layout, Location, Order, OrderLine};

fn order(l: &Layout, id: u32, locs: &[(u16, u16)], qty: u32) -> Order {
    Order {
        id,
        lines: locs
            .iter()
            .map(|&(aisle, bay)| OrderLine {
                sku: format!("SKU-{}", id),
                qty,
                loc: l.id_of(Location { aisle, bay, level: 0 }).unwrap(),
            })
            .collect(),
    }
}

#[test]
fn groups_nearby_orders() {
    let l = Layout::new(6, 20, 1, 30, 10);
    let o = DistanceOracle::new(&l);
    let orders = vec![
        order(&l, 1, &[(0, 2)], 1),
        order(&l, 2, &[(5, 18)], 1),
        order(&l, 3, &[(0, 3)], 1),
        order(&l, 4, &[(5, 17)], 1),
        order(&l, 5, &[(0, 1), (1, 4)], 1),
    ];
    let b = form_batches(&o, &orders, &BatchParams { max_orders: 3, max_units: 100 });
    let ids: Vec<Vec<u32>> = b.iter().map(|x| x.order_ids.clone()).collect();
    assert_eq!(ids, vec![vec![1, 3, 5], vec![2, 4]]);
}

#[test]
fn respects_unit_capacity_and_oversized_seed() {
    let l = Layout::new(2, 10, 1, 30, 10);
    let o = DistanceOracle::new(&l);
    let orders = vec![
        order(&l, 1, &[(0, 1)], 30),
        order(&l, 2, &[(0, 2)], 8),
        order(&l, 3, &[(0, 3)], 3),
        order(&l, 4, &[(1, 3)], 5),
    ];
    let b = form_batches(&o, &orders, &BatchParams { max_orders: 4, max_units: 10 });
    let ids: Vec<Vec<u32>> = b.iter().map(|x| x.order_ids.clone()).collect();
    assert_eq!(ids, vec![vec![1], vec![2], vec![3, 4]]);
    assert_eq!(b[0].units, 30);
    assert_eq!(b[2].units, 8);
}

#[test]
fn empty_orders_ignored() {
    let l = Layout::new(2, 10, 1, 30, 10);
    let o = DistanceOracle::new(&l);
    let orders = vec![Order { id: 9, lines: vec![] }, order(&l, 3, &[(1, 1)], 1)];
    let b = form_batches(&o, &orders, &BatchParams { max_orders: 2, max_units: 10 });
    assert_eq!(b.len(), 1);
    assert_eq!(b[0].order_ids, vec![3]);
}
