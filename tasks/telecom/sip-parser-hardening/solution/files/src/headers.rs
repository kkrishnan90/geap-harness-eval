//! Typed header accessors.

use crate::error::ParseError;
use crate::message::{Method, SipMessage};
use crate::parser::is_token;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CSeq {
    pub seq: u32,
    pub method: Method,
}

fn param<'a>(value: &'a str, name: &str) -> Option<&'a str> {
    value.split(';').skip(1).find_map(|p| {
        let p = p.trim();
        let (k, v) = p.split_once('=')?;
        if k.trim().eq_ignore_ascii_case(name) {
            Some(v.trim())
        } else {
            None
        }
    })
}

impl SipMessage {
    /// CSeq: sequence number and method.
    pub fn cseq(&self) -> Result<CSeq, ParseError> {
        let v = self.header("CSeq").ok_or(ParseError::MissingHeader("CSeq"))?;
        let parts: Vec<&str> = v.split_whitespace().collect();
        if parts.len() != 2 || !is_token(parts[1]) || !parts[0].bytes().all(|b| b.is_ascii_digit()) {
            return Err(ParseError::InvalidCSeq);
        }
        let seq: u32 = parts[0].parse().map_err(|_| ParseError::InvalidCSeq)?;
        if seq >= 1 << 31 {
            return Err(ParseError::InvalidCSeq);
        }
        let method = Method::from_token(parts[1]);
        if let Some(req) = self.method() {
            if req.as_str() != method.as_str() {
                return Err(ParseError::InvalidCSeq);
            }
        }
        Ok(CSeq { seq, method })
    }

    pub fn call_id(&self) -> Result<&str, ParseError> {
        match self.header("Call-ID") {
            Some(v) if !v.is_empty() => Ok(v),
            _ => Err(ParseError::MissingHeader("Call-ID")),
        }
    }

    /// `branch` parameter of the top-most Via.
    pub fn via_branch(&self) -> Result<Option<String>, ParseError> {
        let v = self.header("Via").ok_or(ParseError::MissingHeader("Via"))?;
        let top = v.split(',').next().unwrap_or("");
        Ok(param(top, "branch").map(str::to_string))
    }

    pub fn from_tag(&self) -> Option<String> {
        self.header("From").and_then(|v| param(v, "tag")).map(str::to_string)
    }

    pub fn to_tag(&self) -> Option<String> {
        self.header("To").and_then(|v| param(v, "tag")).map(str::to_string)
    }

    /// Max-Forwards, if present (0..=255).
    pub fn max_forwards(&self) -> Result<Option<u8>, ParseError> {
        match self.header("Max-Forwards") {
            None => Ok(None),
            Some(v) => {
                let v = v.trim();
                if v.is_empty() || v.len() > 3 || !v.bytes().all(|b| b.is_ascii_digit()) {
                    return Err(ParseError::InvalidMaxForwards);
                }
                v.parse::<u8>().map(Some).map_err(|_| ParseError::InvalidMaxForwards)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use crate::parse;

    const REQ: &[u8] = b"OPTIONS sip:edge.example.com SIP/2.0\r\n\
Via: SIP/2.0/UDP 203.0.113.7:5060;branch=z9hG4bK776asdhds, SIP/2.0/UDP 10.0.0.1;branch=z9hG4bKold\r\n\
Max-Forwards: 70\r\n\
From: <sip:monitor@example.org>;tag=1928301774\r\n\
To: <sip:edge.example.com>\r\n\
Call-ID: a84b4c76e66710@203.0.113.7\r\n\
CSeq: 63104 OPTIONS\r\n\
Content-Length: 0\r\n\r\n";

    #[test]
    fn typed_accessors() {
        let m = parse(REQ).unwrap();
        let c = m.cseq().unwrap();
        assert_eq!(c.seq, 63104);
        assert_eq!(c.method.as_str(), "OPTIONS");
        assert_eq!(m.via_branch().unwrap().as_deref(), Some("z9hG4bK776asdhds"));
        assert_eq!(m.from_tag().as_deref(), Some("1928301774"));
        assert_eq!(m.to_tag(), None);
        assert_eq!(m.call_id().unwrap(), "a84b4c76e66710@203.0.113.7");
    }
}
