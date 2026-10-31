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
    /// Header section is not valid UTF-8.
    InvalidUtf8,
    /// Header line `line` (1-based, start line = 1) is malformed.
    MalformedHeader { line: usize },
    /// Start line or a header field exceeds `Limits::max_line_len`.
    HeaderTooLong,
    /// More than `Limits::max_headers` header fields.
    TooManyHeaders,
    /// Content-Length is not a valid decimal, overflows, or is repeated with different values.
    InvalidContentLength,
    /// Body larger than `Limits::max_body`.
    BodyTooLarge,
    /// Fewer body bytes than Content-Length announces.
    BodyLengthMismatch,
    /// CSeq header is malformed.
    InvalidCSeq,
    /// Max-Forwards is not a number in 0..=255.
    InvalidMaxForwards,
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
