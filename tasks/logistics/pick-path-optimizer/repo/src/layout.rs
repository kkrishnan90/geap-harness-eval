//! Warehouse geometry.
//!
//! Aisles are parallel and numbered `0..aisles`. Each aisle has bay positions
//! `1..=bays` (bay 0 is the point where the aisle meets the front cross-aisle)
//! and `levels` shelf levels (level does not change travel distance). Pickers
//! change aisle through the front cross-aisle (y = 0) or the back cross-aisle
//! (y = (bays + 1) * bay_pitch). The depot is aisle 0, bay 0, level 0.

pub type LocId = u32;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Location {
    pub aisle: u16,
    pub bay: u16,
    pub level: u8,
}

#[derive(Clone, Debug)]
pub struct Layout {
    aisles: u16,
    bays: u16,
    levels: u8,
    aisle_pitch_dm: u32,
    bay_pitch_dm: u32,
}

impl Layout {
    pub fn new(aisles: u16, bays: u16, levels: u8, aisle_pitch_dm: u32, bay_pitch_dm: u32) -> Layout {
        assert!(aisles > 0 && bays > 0 && levels > 0, "empty layout");
        Layout { aisles, bays, levels, aisle_pitch_dm, bay_pitch_dm }
    }

    pub fn aisles(&self) -> u16 {
        self.aisles
    }

    pub fn bays(&self) -> u16 {
        self.bays
    }

    pub fn levels(&self) -> u8 {
        self.levels
    }

    pub fn depot(&self) -> LocId {
        0
    }

    pub fn location_count(&self) -> u32 {
        self.aisles as u32 * (self.bays as u32 + 1) * self.levels as u32
    }

    pub fn id_of(&self, loc: Location) -> Option<LocId> {
        if loc.aisle >= self.aisles || loc.bay > self.bays || loc.level >= self.levels {
            return None;
        }
        Some((loc.aisle as u32 * (self.bays as u32 + 1) + loc.bay as u32) * self.levels as u32 + loc.level as u32)
    }

    pub fn location(&self, id: LocId) -> Option<Location> {
        if id >= self.location_count() {
            return None;
        }
        let levels = self.levels as u32;
        let per_aisle = self.bays as u32 + 1;
        let level = (id % levels) as u8;
        let rest = id / levels;
        Some(Location { aisle: (rest / per_aisle) as u16, bay: (rest % per_aisle) as u16, level })
    }

    /// Location label as printed on the rack: `A03-B12-L1` (1-based level).
    pub fn label(&self, id: LocId) -> String {
        match self.location(id) {
            Some(l) => format!("A{:02}-B{:02}-L{}", l.aisle, l.bay, l.level as u32 + 1),
            None => format!("?{}", id),
        }
    }

    /// Walking distance in decimetres. Only `oracle::DistanceOracle` may call this.
    pub(crate) fn travel_dm(&self, a: LocId, b: LocId) -> u32 {
        let la = self.location(a).expect("unknown location");
        let lb = self.location(b).expect("unknown location");
        let ya = la.bay as u32 * self.bay_pitch_dm;
        let yb = lb.bay as u32 * self.bay_pitch_dm;
        if la.aisle == lb.aisle {
            return ya.abs_diff(yb);
        }
        let back = (self.bays as u32 + 1) * self.bay_pitch_dm;
        let across = (la.aisle as u32).abs_diff(lb.aisle as u32) * self.aisle_pitch_dm;
        let via_front = ya + yb;
        let via_back = (back - ya) + (back - yb);
        across + via_front.min(via_back)
    }
}
