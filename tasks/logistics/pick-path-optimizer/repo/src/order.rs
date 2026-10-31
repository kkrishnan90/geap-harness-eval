//! Customer orders as released by the WMS for a wave.

use crate::layout::LocId;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct OrderLine {
    pub sku: String,
    pub qty: u32,
    pub loc: LocId,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Order {
    pub id: u32,
    pub lines: Vec<OrderLine>,
}

impl Order {
    /// Total units (trolley capacity is measured in units).
    pub fn units(&self) -> u32 {
        self.lines.iter().map(|l| l.qty).sum()
    }

    /// The order's anchor location used for batching: its smallest pick `LocId`
    /// (`None` for an order without lines).
    pub fn anchor(&self) -> Option<LocId> {
        self.lines.iter().map(|l| l.loc).min()
    }

    /// Distinct pick locations, ascending.
    pub fn locations(&self) -> Vec<LocId> {
        let mut v: Vec<LocId> = self.lines.iter().map(|l| l.loc).collect();
        v.sort_unstable();
        v.dedup();
        v
    }
}
