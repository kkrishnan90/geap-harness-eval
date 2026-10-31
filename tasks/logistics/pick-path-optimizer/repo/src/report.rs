//! Pick-list rendering for the handheld terminals (fixed 40-column screens).

use crate::layout::Layout;
use crate::order::Order;
use crate::route::Route;

/// One line per stop in route order: `NN LABEL        SKU xQTY (order)`.
/// Lines of several orders at the same location are listed in order-id order.
pub fn pick_list(layout: &Layout, route: &Route, orders: &[Order]) -> Vec<String> {
    let mut sorted: Vec<&Order> = orders.iter().collect();
    sorted.sort_by_key(|o| o.id);
    let mut out = Vec::new();
    for (n, stop) in route.stops.iter().enumerate() {
        for o in &sorted {
            for line in o.lines.iter().filter(|l| l.loc == *stop) {
                let mut sku = line.sku.clone();
                sku.truncate(12);
                out.push(format!("{:02} {:<11} {:<12} x{:<3} ({})", n + 1, layout.label(*stop), sku, line.qty, o.id));
            }
        }
    }
    out
}
