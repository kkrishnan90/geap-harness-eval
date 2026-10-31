//! Server transaction matching key (RFC 3261 §17.2.3, magic-cookie branches only).

use crate::error::ParseError;
use crate::message::{Method, SipMessage};

pub const MAGIC_COOKIE: &str = "z9hG4bK";

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct TransactionKey {
    pub branch: String,
    pub sent_by: String,
    /// ACK and CANCEL match the INVITE transaction's method for lookup purposes.
    pub method: String,
}

fn sent_by(via: &str) -> Option<String> {
    // "SIP/2.0/UDP host:port;params" -> "host:port"
    let top = via.split(',').next()?.trim();
    let after_proto = top.split_whitespace().nth(1)?;
    Some(after_proto.split(';').next()?.to_ascii_lowercase())
}

pub fn server_key(msg: &SipMessage) -> Result<Option<TransactionKey>, ParseError> {
    let method = match msg.method() {
        Some(m) => m.clone(),
        None => return Ok(None),
    };
    let branch = match msg.via_branch()? {
        Some(b) if b.starts_with(MAGIC_COOKIE) => b,
        _ => return Ok(None),
    };
    let via = msg.header("Via").unwrap_or("");
    let sent_by = sent_by(via).ok_or(ParseError::MissingHeader("Via"))?;
    let method = match method {
        Method::Ack | Method::Cancel => "INVITE".to_string(),
        m => m.as_str().to_string(),
    };
    Ok(Some(TransactionKey { branch, sent_by, method }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parse;

    #[test]
    fn ack_matches_invite() {
        let inv = parse(b"INVITE sip:b@x SIP/2.0\r\nVia: SIP/2.0/UDP Pc33.Example.com;branch=z9hG4bKnashds8\r\n\r\n").unwrap();
        let ack = parse(b"ACK sip:b@x SIP/2.0\r\nv: SIP/2.0/UDP pc33.example.com;branch=z9hG4bKnashds8\r\n\r\n").unwrap();
        assert_eq!(server_key(&inv).unwrap(), server_key(&ack).unwrap());
    }

    #[test]
    fn legacy_branch_has_no_key() {
        let m = parse(b"OPTIONS sip:b@x SIP/2.0\r\nVia: SIP/2.0/UDP h;branch=1234\r\n\r\n").unwrap();
        assert_eq!(server_key(&m).unwrap(), None);
    }
}
