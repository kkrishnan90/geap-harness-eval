//! Wire bytes -> SipMessage.
//!
//! Hardened for untrusted input: never panics, never allocates more than the
//! input size, and enforces `Limits`.

use crate::error::ParseError;
use crate::limits::Limits;
use crate::message::{canonical_name, Method, SipMessage, StartLine};
use crate::uri::SipUri;

/// Parse with the default production limits.
pub fn parse(bytes: &[u8]) -> Result<SipMessage, ParseError> {
    parse_with_limits(bytes, &Limits::default())
}

fn find(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    haystack.windows(needle.len()).position(|w| w == needle)
}

pub(crate) fn is_token(s: &str) -> bool {
    !s.is_empty() && s.bytes().all(|b| b.is_ascii_alphanumeric() || b"-.!%*_+`'~".contains(&b))
}

/// Parse one SIP message (one UDP datagram or one framed TCP message).
pub fn parse_with_limits(bytes: &[u8], limits: &Limits) -> Result<SipMessage, ParseError> {
    let hdr_end = find(bytes, b"\r\n\r\n").ok_or(ParseError::Incomplete)?;
    let head = std::str::from_utf8(&bytes[..hdr_end]).map_err(|_| ParseError::InvalidUtf8)?;
    let mut lines = head.split("\r\n");
    let first = lines.next().unwrap_or("");
    if first.len() > limits.max_line_len {
        return Err(ParseError::HeaderTooLong);
    }
    if first.contains(['\r', '\n']) {
        return Err(ParseError::InvalidStartLine);
    }
    let start = parse_start_line(first)?;

    let mut headers: Vec<(String, String)> = Vec::new();
    let mut current_raw_len = 0usize;
    for (i, line) in lines.enumerate() {
        let line_no = i + 2;
        if line.len() > limits.max_line_len {
            return Err(ParseError::HeaderTooLong);
        }
        if line.contains(['\r', '\n']) {
            return Err(ParseError::MalformedHeader { line: line_no });
        }
        if line.starts_with(' ') || line.starts_with('\t') {
            let last = headers.last_mut().ok_or(ParseError::MalformedHeader { line: line_no })?;
            current_raw_len += line.len();
            if current_raw_len > limits.max_line_len {
                return Err(ParseError::HeaderTooLong);
            }
            let cont = line.trim();
            if !cont.is_empty() {
                if !last.1.is_empty() {
                    last.1.push(' ');
                }
                last.1.push_str(cont);
            }
            continue;
        }
        let colon = line.find(':').ok_or(ParseError::MalformedHeader { line: line_no })?;
        let name = line[..colon].trim_end_matches([' ', '\t']);
        if !is_token(name) {
            return Err(ParseError::MalformedHeader { line: line_no });
        }
        if headers.len() >= limits.max_headers {
            return Err(ParseError::TooManyHeaders);
        }
        current_raw_len = line.len();
        headers.push((name.to_string(), line[colon + 1..].trim().to_string()));
    }

    let rest = &bytes[hdr_end + 4..];
    let mut content_length: Option<usize> = None;
    for (n, v) in &headers {
        if canonical_name(n) != "content-length" {
            continue;
        }
        let v = v.trim();
        if v.is_empty() || !v.bytes().all(|b| b.is_ascii_digit()) {
            return Err(ParseError::InvalidContentLength);
        }
        let parsed: usize = v.parse().map_err(|_| ParseError::InvalidContentLength)?;
        match content_length {
            Some(prev) if prev != parsed => return Err(ParseError::InvalidContentLength),
            _ => content_length = Some(parsed),
        }
    }
    let body = match content_length {
        Some(n) => {
            if n > limits.max_body {
                return Err(ParseError::BodyTooLarge);
            }
            if rest.len() < n {
                return Err(ParseError::BodyLengthMismatch);
            }
            rest[..n].to_vec()
        }
        None => {
            if rest.len() > limits.max_body {
                return Err(ParseError::BodyTooLarge);
            }
            rest.to_vec()
        }
    };
    Ok(SipMessage { start, headers, body })
}

fn parse_start_line(line: &str) -> Result<StartLine, ParseError> {
    if line.starts_with("SIP/") {
        let mut parts = line.splitn(3, ' ');
        let version = parts.next().unwrap_or("");
        if version != "SIP/2.0" {
            return Err(ParseError::UnsupportedVersion);
        }
        let code_str = parts.next().ok_or(ParseError::InvalidStartLine)?;
        if code_str.len() != 3 || !code_str.bytes().all(|b| b.is_ascii_digit()) {
            return Err(ParseError::InvalidStartLine);
        }
        let code: u16 = code_str.parse().map_err(|_| ParseError::InvalidStartLine)?;
        if !(100..=699).contains(&code) {
            return Err(ParseError::InvalidStartLine);
        }
        let reason = parts.next().unwrap_or("").to_string();
        Ok(StartLine::Response { code, reason })
    } else {
        let parts: Vec<&str> = line.split(' ').collect();
        if parts.len() != 3 || !is_token(parts[0]) {
            return Err(ParseError::InvalidStartLine);
        }
        if parts[2] != "SIP/2.0" {
            return Err(ParseError::UnsupportedVersion);
        }
        let uri = SipUri::parse(parts[1])?;
        Ok(StartLine::Request { method: Method::from_token(parts[0]), uri })
    }
}
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn minimal_response() {
        let m = parse(b"SIP/2.0 200 OK\r\nContent-Length: 0\r\n\r\n").unwrap();
        assert_eq!(m.start, StartLine::Response { code: 200, reason: "OK".into() });
        assert!(m.body.is_empty());
    }

    #[test]
    fn missing_blank_line_is_incomplete() {
        assert_eq!(parse(b"SIP/2.0 200 OK\r\nContent-Length: 0\r\n"), Err(ParseError::Incomplete));
    }

    #[test]
    fn wrong_version() {
        assert_eq!(parse(b"SIP/3.0 200 OK\r\n\r\n"), Err(ParseError::UnsupportedVersion));
        assert_eq!(parse(b"INVITE sip:a@b SIP/1.0\r\n\r\n"), Err(ParseError::UnsupportedVersion));
    }

    #[test]
    fn header_without_colon() {
        assert_eq!(
            parse(b"SIP/2.0 200 OK\r\nVia SIP/2.0/UDP x\r\n\r\n"),
            Err(ParseError::MalformedHeader { line: 2 })
        );
    }
}
