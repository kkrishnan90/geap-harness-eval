//! Wire bytes -> SipMessage.

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

/// Parse one SIP message (one UDP datagram or one framed TCP message).
pub fn parse_with_limits(bytes: &[u8], _limits: &Limits) -> Result<SipMessage, ParseError> {
    let hdr_end = find(bytes, b"\r\n\r\n").ok_or(ParseError::Incomplete)?;
    let head = std::str::from_utf8(&bytes[..hdr_end]).expect("SIP header section must be UTF-8");
    let mut lines = head.split("\r\n");
    let start = parse_start_line(lines.next().unwrap())?;

    let mut headers: Vec<(String, String)> = Vec::new();
    for (i, line) in lines.enumerate() {
        if line.starts_with(' ') || line.starts_with('\t') {
            // folded continuation of the previous header (RFC 3261 §7.3.1)
            let last = headers.last_mut().unwrap();
            last.1.push(' ');
            last.1.push_str(line.trim());
            continue;
        }
        let colon = line.find(':').ok_or(ParseError::MalformedHeader { line: i + 2 })?;
        let name = line[..colon].trim();
        let value = line[colon + 1..].trim();
        if name.is_empty() {
            return Err(ParseError::MalformedHeader { line: i + 2 });
        }
        headers.push((name.to_string(), value.to_string()));
    }

    let rest = &bytes[hdr_end + 4..];
    let body = match headers.iter().find(|(n, _)| canonical_name(n) == "content-length") {
        Some((_, v)) => {
            let n: usize = v.parse().unwrap();
            let mut b = Vec::with_capacity(n);
            b.extend_from_slice(&rest[..n]);
            b
        }
        None => rest.to_vec(),
    };
    Ok(SipMessage { start, headers, body })
}

fn parse_start_line(line: &str) -> Result<StartLine, ParseError> {
    if line.starts_with("SIP/") {
        let mut parts = line.splitn(3, ' ');
        let version = parts.next().unwrap();
        if version != "SIP/2.0" {
            return Err(ParseError::UnsupportedVersion);
        }
        let code: u16 = parts
            .next()
            .ok_or(ParseError::InvalidStartLine)?
            .parse()
            .map_err(|_| ParseError::InvalidStartLine)?;
        let reason = parts.next().unwrap_or("").to_string();
        Ok(StartLine::Response { code, reason })
    } else {
        let parts: Vec<&str> = line.split(' ').collect();
        if parts.len() != 3 {
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
