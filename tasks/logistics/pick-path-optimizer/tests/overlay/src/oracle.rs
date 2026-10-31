//! Instrumented distance oracle.
//!
//! Every travel distance used by the planner must come from `DistanceOracle::dist`.
//! In production this is a call to the WMS travel-time service; the lookup counter is
//! exported as the `pickplan_distance_lookups_total` metric and budgeted per wave.

use std::cell::Cell;

use crate::layout::{Layout, LocId};

pub struct DistanceOracle<'a> {
    layout: &'a Layout,
    lookups: Cell<u64>,
}

impl<'a> DistanceOracle<'a> {
    pub fn new(layout: &'a Layout) -> DistanceOracle<'a> {
        DistanceOracle { layout, lookups: Cell::new(0) }
    }

    /// Symmetric travel distance in decimetres; `dist(a, a) == 0`. Counts one lookup per call.
    pub fn dist(&self, a: LocId, b: LocId) -> u32 {
        self.lookups.set(self.lookups.get() + 1);
        self.layout.travel_dm(a, b)
    }

    /// Number of `dist` calls since creation or the last `reset`.
    pub fn lookups(&self) -> u64 {
        self.lookups.get()
    }

    pub fn reset(&self) {
        self.lookups.set(0);
    }

    pub fn layout(&self) -> &Layout {
        self.layout
    }
}
