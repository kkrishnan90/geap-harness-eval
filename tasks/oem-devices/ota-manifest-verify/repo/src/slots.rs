//! A/B slot bookkeeping. The bootloader tries a freshly written slot up to
//! `MAX_BOOT_ATTEMPTS` times before falling back to the previous one.

use crate::version::Version;

pub const MAX_BOOT_ATTEMPTS: u8 = 3;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Slot {
    A,
    B,
}

impl Slot {
    pub fn other(self) -> Slot {
        match self {
            Slot::A => Slot::B,
            Slot::B => Slot::A,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SlotState {
    Empty,
    Good(Version),
    /// Written, waiting for the bootloader to try it.
    Pending { version: Version, attempts_left: u8 },
    Bad(Version),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SlotError {
    UpdateInProgress,
    NothingPending,
}

#[derive(Debug, Clone)]
pub struct SlotTable {
    active: Slot,
    a: SlotState,
    b: SlotState,
}

impl SlotTable {
    pub fn new(active: Slot, active_version: Version) -> Self {
        let mut t = SlotTable { active, a: SlotState::Empty, b: SlotState::Empty };
        *t.state_mut(active) = SlotState::Good(active_version);
        t
    }

    pub fn active(&self) -> Slot {
        self.active
    }

    pub fn state(&self, slot: Slot) -> SlotState {
        match slot {
            Slot::A => self.a,
            Slot::B => self.b,
        }
    }

    fn state_mut(&mut self, slot: Slot) -> &mut SlotState {
        match slot {
            Slot::A => &mut self.a,
            Slot::B => &mut self.b,
        }
    }

    /// Record that a verified image was written to the inactive slot.
    pub fn mark_written(&mut self, version: Version) -> Result<Slot, SlotError> {
        let target = self.active.other();
        if matches!(self.state(target), SlotState::Pending { .. }) {
            return Err(SlotError::UpdateInProgress);
        }
        *self.state_mut(target) = SlotState::Pending { version, attempts_left: MAX_BOOT_ATTEMPTS };
        Ok(target)
    }

    /// Bootloader consumed one attempt on the pending slot. Returns the slot to boot.
    pub fn boot_attempt(&mut self) -> Slot {
        let target = self.active.other();
        if let SlotState::Pending { version, attempts_left } = self.state(target) {
            if attempts_left == 0 {
                *self.state_mut(target) = SlotState::Bad(version);
                return self.active;
            }
            *self.state_mut(target) = SlotState::Pending { version, attempts_left: attempts_left - 1 };
            return target;
        }
        self.active
    }

    /// The pending slot booted and passed health checks: make it active.
    pub fn commit(&mut self) -> Result<Slot, SlotError> {
        let target = self.active.other();
        match self.state(target) {
            SlotState::Pending { version, .. } => {
                *self.state_mut(target) = SlotState::Good(version);
                self.active = target;
                Ok(target)
            }
            _ => Err(SlotError::NothingPending),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn write_and_commit() {
        let mut t = SlotTable::new(Slot::A, Version::new(1, 0, 0));
        assert_eq!(t.mark_written(Version::new(1, 1, 0)), Ok(Slot::B));
        assert_eq!(t.mark_written(Version::new(1, 2, 0)), Err(SlotError::UpdateInProgress));
        assert_eq!(t.boot_attempt(), Slot::B);
        assert_eq!(t.commit(), Ok(Slot::B));
        assert_eq!(t.active(), Slot::B);
        assert_eq!(t.state(Slot::B), SlotState::Good(Version::new(1, 1, 0)));
    }

    #[test]
    fn falls_back_after_attempts() {
        let mut t = SlotTable::new(Slot::B, Version::new(2, 0, 0));
        t.mark_written(Version::new(2, 1, 0)).unwrap();
        for _ in 0..MAX_BOOT_ATTEMPTS {
            assert_eq!(t.boot_attempt(), Slot::A);
        }
        assert_eq!(t.boot_attempt(), Slot::B);
        assert_eq!(t.state(Slot::A), SlotState::Bad(Version::new(2, 1, 0)));
        assert_eq!(t.commit(), Err(SlotError::NothingPending));
    }
}
