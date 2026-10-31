//! On-device OTA update agent.

pub mod hex;
pub mod manifest;
pub mod sha256;
pub mod slots;
pub mod verify;
pub mod version;

pub use manifest::{parse_manifest, Manifest, ManifestError};
pub use verify::{verify_update, DeviceState, VerifiedUpdate, VerifyError};
pub use version::{Version, VersionError};
