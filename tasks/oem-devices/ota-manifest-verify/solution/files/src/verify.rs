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
    /// Anti-rollback floor from secure storage: images with a lower
    /// `security_version` must never be installed.
    pub security_floor: u32,
}

impl DeviceState {
    pub fn new(component: &str, installed_version: Version) -> Self {
        DeviceState { component: component.to_string(), installed_version, security_floor: 0 }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VerifiedUpdate {
    pub component: String,
    pub version: Version,
    pub security_version: u32,
    pub chunks_verified: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum VerifyError {
    ComponentMismatch { expected: String, found: String },
    Rollback { installed: Version, offered: Version },
    AlreadyInstalled(Version),
    SecurityVersionTooLow { floor: u32, offered: u32 },
    SizeMismatch { expected: u64, actual: u64 },
    ChunkDigestMismatch { index: usize },
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
            VerifyError::Rollback { installed, offered } => {
                write!(f, "version {offered} is older than installed {installed}")
            }
            VerifyError::AlreadyInstalled(v) => write!(f, "version {v} is already installed"),
            VerifyError::SecurityVersionTooLow { floor, offered } => {
                write!(f, "security version {offered} below device floor {floor}")
            }
            VerifyError::ChunkDigestMismatch { index } => write!(f, "digest mismatch in chunk {index}"),
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
    if manifest.version < device.installed_version {
        return Err(VerifyError::Rollback { installed: device.installed_version, offered: manifest.version });
    }
    if manifest.version == device.installed_version {
        return Err(VerifyError::AlreadyInstalled(manifest.version));
    }
    if manifest.security_version < device.security_floor {
        return Err(VerifyError::SecurityVersionTooLow {
            floor: device.security_floor,
            offered: manifest.security_version,
        });
    }
    if image.len() as u64 != manifest.image_size {
        return Err(VerifyError::SizeMismatch { expected: manifest.image_size, actual: image.len() as u64 });
    }
    if !manifest.chunk_sha256.is_empty() {
        let chunk_size = manifest.chunk_size as usize;
        for (index, (chunk, expected)) in image.chunks(chunk_size).zip(&manifest.chunk_sha256).enumerate() {
            if !sha256::ct_eq(&sha256::digest(chunk), expected) {
                return Err(VerifyError::ChunkDigestMismatch { index });
            }
        }
    }
    let digest = sha256::digest(image);
    if !sha256::ct_eq(&digest, &manifest.image_sha256) {
        return Err(VerifyError::ImageDigestMismatch);
    }
    Ok(VerifiedUpdate {
        component: manifest.component.clone(),
        version: manifest.version,
        security_version: manifest.security_version,
        chunks_verified: manifest.chunk_sha256.len(),
    })
}
