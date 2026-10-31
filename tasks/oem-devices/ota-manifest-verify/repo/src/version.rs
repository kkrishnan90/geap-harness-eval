//! Firmware version numbers: `MAJOR.MINOR.PATCH`, each a decimal `u32`.

use std::fmt;
use std::str::FromStr;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct Version {
    pub major: u32,
    pub minor: u32,
    pub patch: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum VersionError {
    Empty,
    WrongPartCount(usize),
    BadNumber(String),
}

impl Version {
    pub const fn new(major: u32, minor: u32, patch: u32) -> Self {
        Version { major, minor, patch }
    }
}

impl FromStr for Version {
    type Err = VersionError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        let s = s.trim();
        if s.is_empty() {
            return Err(VersionError::Empty);
        }
        let parts: Vec<&str> = s.split('.').collect();
        if parts.len() != 3 {
            return Err(VersionError::WrongPartCount(parts.len()));
        }
        let mut nums = [0u32; 3];
        for (i, p) in parts.iter().enumerate() {
            if p.is_empty() || !p.bytes().all(|b| b.is_ascii_digit()) {
                return Err(VersionError::BadNumber(p.to_string()));
            }
            nums[i] = p.parse().map_err(|_| VersionError::BadNumber(p.to_string()))?;
        }
        Ok(Version::new(nums[0], nums[1], nums[2]))
    }
}

impl fmt::Display for Version {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}.{}.{}", self.major, self.minor, self.patch)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_and_display() {
        let v: Version = "5.3.10".parse().unwrap();
        assert_eq!(v, Version::new(5, 3, 10));
        assert_eq!(v.to_string(), "5.3.10");
    }

    #[test]
    fn parse_errors() {
        assert_eq!("".parse::<Version>(), Err(VersionError::Empty));
        assert_eq!("1.2".parse::<Version>(), Err(VersionError::WrongPartCount(2)));
        assert!(matches!("1.+2.3".parse::<Version>(), Err(VersionError::BadNumber(_))));
        assert!(matches!("v1.2.3".parse::<Version>(), Err(VersionError::BadNumber(_))));
    }
}
