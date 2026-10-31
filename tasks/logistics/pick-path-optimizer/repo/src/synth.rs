//! Deterministic synthetic data (xorshift64*) for tests and the simulator.

use crate::layout::{Layout, Location};
use crate::order::{Order, OrderLine};

pub struct Rng(u64);

impl Rng {
    pub fn new(seed: u64) -> Rng {
        Rng(seed.wrapping_mul(0x9E37_79B9_7F4A_7C15) | 1)
    }

    pub fn next_u64(&mut self) -> u64 {
        let mut x = self.0;
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        self.0 = x;
        x.wrapping_mul(0x2545_F491_4F6C_DD1D)
    }

    /// Uniform in `0..n` (n > 0).
    pub fn below(&mut self, n: u32) -> u32 {
        (self.next_u64() % n as u64) as u32
    }
}

/// The DC-07 high-bay module used in the KPI reports: 12 aisles x 40 bays x 4 levels,
/// aisles 30 dm apart, bays 13 dm wide.
pub fn dc07_layout() -> Layout {
    Layout::new(12, 40, 4, 30, 13)
}

/// `n` orders with ids 1..=n, 1..=max_lines lines each, 1..=4 units per line.
pub fn orders(layout: &Layout, seed: u64, n: u32, max_lines: u32) -> Vec<Order> {
    let mut rng = Rng::new(seed);
    (1..=n)
        .map(|id| {
            let lines = 1 + rng.below(max_lines);
            Order {
                id,
                lines: (0..lines)
                    .map(|_| {
                        let loc = Location {
                            aisle: rng.below(layout.aisles() as u32) as u16,
                            bay: 1 + rng.below(layout.bays() as u32) as u16,
                            level: rng.below(layout.levels() as u32) as u8,
                        };
                        OrderLine {
                            sku: format!("SKU-{:05}", rng.below(5000)),
                            qty: 1 + rng.below(4),
                            loc: layout.id_of(loc).unwrap(),
                        }
                    })
                    .collect(),
            }
        })
        .collect()
}

/// `n` random pick locations (may repeat).
pub fn picks(layout: &Layout, seed: u64, n: u32) -> Vec<u32> {
    let mut rng = Rng::new(seed ^ 0xA5A5);
    (0..n)
        .map(|_| {
            let loc = Location {
                aisle: rng.below(layout.aisles() as u32) as u16,
                bay: 1 + rng.below(layout.bays() as u32) as u16,
                level: rng.below(layout.levels() as u32) as u8,
            };
            layout.id_of(loc).unwrap()
        })
        .collect()
}
