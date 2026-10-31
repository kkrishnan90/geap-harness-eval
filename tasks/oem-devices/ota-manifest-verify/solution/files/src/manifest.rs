//! Update manifest parser. See `docs/manifest-format.md`.

use std::collections::HashMap;
use std::fmt;

use crate::hex;
use crate::sha256::Digest;
use crate::version::Version;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Manifest {
    pub format: u32,
    pub component: String,
    pub version: Version,
    pub image_size: u64,
    pub image_sha256: Digest,
    /// Anti-rollback counter of the image (format 2; 0 for format 1).
    pub security_version: u32,
    /// Size of each verification chunk in bytes (format 2; 0 for format 1).
    pub chunk_size: u64,
    /// SHA-256 of every chunk, index 0 first (format 2; empty for format 1).
    pub chunk_sha256: Vec<Digest>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ManifestError {
    /// Line without `=` (1-based line number).
    Syntax { line: usize },
    DuplicateKey(String),
    MissingKey(String),
    InvalidValue { key: String, value: String },
    UnsupportedFormat(u32),
    /// Number of `chunk.N` entries differs from ceil(image_size / chunk_size).
    ChunkCountMismatch { expected: usize, found: usize },
    /// `chunk.N` entry missing for this index.
    MissingChunk(usize),
}

impl fmt::Display for ManifestError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ManifestError::Syntax { line } => write!(f, "syntax error on line {line}"),
            ManifestError::DuplicateKey(k) => write!(f, "duplicate key {k}"),
            ManifestError::MissingKey(k) => write!(f, "missing key {k}"),
            ManifestError::InvalidValue { key, value } => write!(f, "invalid value {value:?} for {key}"),
            ManifestError::UnsupportedFormat(n) => write!(f, "unsupported manifest format {n}"),
            ManifestError::ChunkCountMismatch { expected, found } => {
                write!(f, "manifest lists {found} chunks, image needs {expected}")
            }
            ManifestError::MissingChunk(i) => write!(f, "missing digest for chunk {i}"),
        }
    }
}

impl std::error::Error for ManifestError {}

pub(crate) struct Fields<'a> {
    map: HashMap<&'a str, &'a str>,
}

impl<'a> Fields<'a> {
    pub(crate) fn parse(text: &'a str) -> Result<Self, ManifestError> {
        let mut map = HashMap::new();
        for (idx, raw) in text.lines().enumerate() {
            let line = raw.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            let (k, v) = line.split_once('=').ok_or(ManifestError::Syntax { line: idx + 1 })?;
            let (k, v) = (k.trim(), v.trim());
            if k.is_empty() {
                return Err(ManifestError::Syntax { line: idx + 1 });
            }
            if map.insert(k, v).is_some() {
                return Err(ManifestError::DuplicateKey(k.to_string()));
            }
        }
        Ok(Fields { map })
    }

    pub(crate) fn get(&self, key: &str) -> Option<&'a str> {
        self.map.get(key).copied()
    }

    pub(crate) fn entries(&self) -> impl Iterator<Item = (&'a str, &'a str)> + '_ {
        self.map.iter().map(|(k, v)| (*k, *v))
    }

    pub(crate) fn require(&self, key: &str) -> Result<&'a str, ManifestError> {
        self.get(key).ok_or_else(|| ManifestError::MissingKey(key.to_string()))
    }
}

pub(crate) fn invalid(key: &str, value: &str) -> ManifestError {
    ManifestError::InvalidValue { key: key.to_string(), value: value.to_string() }
}

pub(crate) fn parse_u64(key: &str, value: &str) -> Result<u64, ManifestError> {
    if value.is_empty() || !value.bytes().all(|b| b.is_ascii_digit()) {
        return Err(invalid(key, value));
    }
    value.parse().map_err(|_| invalid(key, value))
}

pub(crate) fn parse_digest(key: &str, value: &str) -> Result<Digest, ManifestError> {
    hex::decode_fixed::<32>(value).ok_or_else(|| invalid(key, value))
}

pub fn parse_manifest(text: &str) -> Result<Manifest, ManifestError> {
    let fields = Fields::parse(text)?;

    let format_raw = fields.require("format")?;
    let format = parse_u64("format", format_raw)?;
    if format != 1 && format != 2 {
        return Err(ManifestError::UnsupportedFormat(format.min(u32::MAX as u64) as u32));
    }

    let component = fields.require("component")?;
    if component.is_empty() || !component.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_') {
        return Err(invalid("component", component));
    }
    let version_raw = fields.require("version")?;
    let version: Version = version_raw.parse().map_err(|_| invalid("version", version_raw))?;
    let image_size = parse_u64("image_size", fields.require("image_size")?)?;
    let image_sha256 = parse_digest("image_sha256", fields.require("image_sha256")?)?;

    let mut manifest = Manifest {
        format: format as u32,
        component: component.to_string(),
        version,
        image_size,
        image_sha256,
        security_version: 0,
        chunk_size: 0,
        chunk_sha256: Vec::new(),
    };
    if format == 2 {
        parse_v2_fields(&fields, &mut manifest)?;
    }
    Ok(manifest)
}

fn parse_v2_fields(fields: &Fields<'_>, m: &mut Manifest) -> Result<(), ManifestError> {
    let sv_raw = fields.require("security_version")?;
    let sv = parse_u64("security_version", sv_raw)?;
    m.security_version = u32::try_from(sv).map_err(|_| invalid("security_version", sv_raw))?;

    let cs_raw = fields.require("chunk_size")?;
    let chunk_size = parse_u64("chunk_size", cs_raw)?;
    if chunk_size == 0 {
        return Err(invalid("chunk_size", cs_raw));
    }
    m.chunk_size = chunk_size;

    let mut chunks: Vec<(usize, Digest)> = Vec::new();
    for (key, value) in fields.entries() {
        if let Some(idx) = key.strip_prefix("chunk.") {
            if idx.is_empty() || !idx.bytes().all(|b| b.is_ascii_digit()) {
                return Err(invalid(key, value));
            }
            let idx: usize = idx.parse().map_err(|_| invalid(key, value))?;
            chunks.push((idx, parse_digest(key, value)?));
        }
    }
    let expected = m.image_size.div_ceil(chunk_size);
    let expected = usize::try_from(expected).map_err(|_| invalid("chunk_size", cs_raw))?;
    if chunks.len() != expected {
        return Err(ManifestError::ChunkCountMismatch { expected, found: chunks.len() });
    }
    chunks.sort_by_key(|(i, _)| *i);
    let mut out = Vec::with_capacity(expected);
    for (want, (idx, digest)) in chunks.into_iter().enumerate() {
        if idx != want {
            return Err(ManifestError::MissingChunk(want));
        }
        out.push(digest);
    }
    m.chunk_sha256 = out;
    Ok(())
}
