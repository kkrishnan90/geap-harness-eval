//! Resource limits applied while parsing untrusted input.

/// Parser limits. Defaults are the SBC production values.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Limits {
    /// Maximum number of header fields (after unfolding).
    pub max_headers: usize,
    /// Maximum length in bytes of the start line and of any header field
    /// (all its physical lines together, CRLFs excluded).
    pub max_line_len: usize,
    /// Maximum body size in bytes.
    pub max_body: usize,
}

impl Default for Limits {
    fn default() -> Self {
        Limits { max_headers: 64, max_line_len: 4096, max_body: 65536 }
    }
}
