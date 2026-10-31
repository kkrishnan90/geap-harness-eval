//! ABC velocity classification (nightly re-slotting proposal job).

use std::collections::HashMap;

use crate::order::Order;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum VelocityClass {
    A,
    B,
    C,
}

/// Classifies SKUs by pick-line frequency: SKUs are ranked by number of order lines
/// (descending, ties by SKU name); the top SKUs covering the first 80 % of lines are A,
/// the next 15 % B, the rest C. Returns (sku, lines, class) in rank order.
pub fn classify(orders: &[Order]) -> Vec<(String, u32, VelocityClass)> {
    let mut freq: HashMap<&str, u32> = HashMap::new();
    let mut total = 0u32;
    for o in orders {
        for l in &o.lines {
            *freq.entry(l.sku.as_str()).or_insert(0) += 1;
            total += 1;
        }
    }
    let mut ranked: Vec<(&str, u32)> = freq.into_iter().collect();
    ranked.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(b.0)));

    let mut out = Vec::with_capacity(ranked.len());
    let mut cumulative = 0u32;
    for (sku, n) in ranked {
        // class by the share of lines *before* this SKU
        let share = if total == 0 { 0.0 } else { cumulative as f64 / total as f64 };
        let class = if share < 0.80 {
            VelocityClass::A
        } else if share < 0.95 {
            VelocityClass::B
        } else {
            VelocityClass::C
        };
        cumulative += n;
        out.push((sku.to_string(), n, class));
    }
    out
}
