//! Pre-install verification of an update against the device state.

use std::fmt;

use crate::manifest::Manifest;
use crate::sha256;
use crate::version::Version;

/// What the device knows about itself (read from the active slot and secure storage).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeviceState {
    pub component: String,
    pub installed_version: Version,
}

impl DeviceState {
    pub fn new(component: &str, installed_version: Version) -> Self {
        DeviceState { component: component.to_string(), installed_version }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VerifiedUpdate {
    pub component: String,
    pub version: Version,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum VerifyError {
    ComponentMismatch { expected: String, found: String },
    SizeMismatch { expected: u64, actual: u64 },
    ImageDigestMismatch,
}

impl fmt::Display for VerifyError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            VerifyError::ComponentMismatch { expected, found } => {
                write!(f, "manifest is for {found}, device runs {expected}")
            }
            VerifyError::SizeMismatch { expected, actual } => {
                write!(f, "image is {actual} bytes, manifest says {expected}")
            }
            VerifyError::ImageDigestMismatch => write!(f, "image digest mismatch"),
        }
    }
}

impl std::error::Error for VerifyError {}

/// Verify `image` against `manifest` for installation on `device`.
pub fn verify_update(manifest: &Manifest, image: &[u8], device: &DeviceState) -> Result<VerifiedUpdate, VerifyError> {
    if manifest.component != device.component {
        return Err(VerifyError::ComponentMismatch {
            expected: device.component.clone(),
            found: manifest.component.clone(),
        });
    }
    if image.len() as u64 != manifest.image_size {
        return Err(VerifyError::SizeMismatch { expected: manifest.image_size, actual: image.len() as u64 });
    }
    let digest = sha256::digest(image);
    if !sha256::ct_eq(&digest, &manifest.image_sha256) {
        return Err(VerifyError::ImageDigestMismatch);
    }
    Ok(VerifiedUpdate { component: manifest.component.clone(), version: manifest.version })
}
