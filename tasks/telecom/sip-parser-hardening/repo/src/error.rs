use std::fmt;

/// Why a message (or a header value) could not be parsed.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ParseError {
    /// No complete header section (missing empty line).
    Incomplete,
    /// Start line is not a valid request or status line.
    InvalidStartLine,
    /// Protocol version other than SIP/2.0.
    UnsupportedVersion,
    /// Header line `line` (1-based, start line = 1) is malformed.
    MalformedHeader { line: usize },
    /// CSeq header is malformed.
    InvalidCSeq,
    /// URI is malformed.
    InvalidUri,
    /// A mandatory header is absent.
    MissingHeader(&'static str),
}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{:?}", self)
    }
}

impl std::error::Error for ParseError {}
