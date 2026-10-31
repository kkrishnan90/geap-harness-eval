//! SIP / SIPS URI parsing (RFC 3261 §19.1), subset used by the edge proxy.

use crate::error::ParseError;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SipUri {
    pub secure: bool,
    pub user: Option<String>,
    /// Host name, IPv4 address, or bracketed IPv6 reference (`[2001:db8::1]`).
    pub host: String,
    pub port: Option<u16>,
    /// URI parameters in order (`;transport=tcp;lr` -> [("transport", Some("tcp")), ("lr", None)]).
    pub params: Vec<(String, Option<String>)>,
}

impl SipUri {
    pub fn parse(s: &str) -> Result<SipUri, ParseError> {
        let (secure, rest) = if let Some(r) = s.strip_prefix("sips:") {
            (true, r)
        } else if let Some(r) = s.strip_prefix("sip:") {
            (false, r)
        } else {
            return Err(ParseError::InvalidUri);
        };

        let (main, params_str) = match rest.find(';') {
            Some(i) => (&rest[..i], Some(&rest[i + 1..])),
            None => (rest, None),
        };
        let (user, hostport) = match main.rfind('@') {
            Some(i) => {
                let user = &main[..i];
                if user.is_empty() {
                    return Err(ParseError::InvalidUri);
                }
                (Some(user.to_string()), &main[i + 1..])
            }
            None => (None, main),
        };

        let (host, port_str) = if hostport.starts_with('[') {
            let end = hostport.find(']').ok_or(ParseError::InvalidUri)?;
            let inner = &hostport[1..end];
            if inner.is_empty()
                || !inner.contains(':')
                || !inner.bytes().all(|b| b.is_ascii_hexdigit() || b == b':' || b == b'.')
            {
                return Err(ParseError::InvalidUri);
            }
            let after = &hostport[end + 1..];
            let port_str = if after.is_empty() {
                None
            } else {
                Some(after.strip_prefix(':').ok_or(ParseError::InvalidUri)?)
            };
            (&hostport[..=end], port_str)
        } else {
            let (h, p) = match hostport.find(':') {
                Some(i) => (&hostport[..i], Some(&hostport[i + 1..])),
                None => (hostport, None),
            };
            if h.is_empty() || !h.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'.' || b == b'-') {
                return Err(ParseError::InvalidUri);
            }
            (h, p)
        };
        let port = match port_str {
            None => None,
            Some(p) => {
                if p.is_empty() || p.len() > 5 || !p.bytes().all(|b| b.is_ascii_digit()) {
                    return Err(ParseError::InvalidUri);
                }
                let n: u32 = p.parse().map_err(|_| ParseError::InvalidUri)?;
                if n == 0 || n > 65535 {
                    return Err(ParseError::InvalidUri);
                }
                Some(n as u16)
            }
        };

        let mut params = Vec::new();
        if let Some(ps) = params_str {
            for p in ps.split(';') {
                let (name, value) = match p.find('=') {
                    Some(i) => (&p[..i], Some(p[i + 1..].to_string())),
                    None => (p, None),
                };
                if name.is_empty() {
                    return Err(ParseError::InvalidUri);
                }
                params.push((name.to_string(), value));
            }
        }
        Ok(SipUri { secure, user, host: host.to_string(), port, params })
    }

    pub fn param(&self, name: &str) -> Option<Option<&str>> {
        self.params
            .iter()
            .find(|(n, _)| n.eq_ignore_ascii_case(name))
            .map(|(_, v)| v.as_deref())
    }

    /// Port to use for this URI (explicit or the scheme default).
    pub fn effective_port(&self) -> u16 {
        self.port.unwrap_or(if self.secure { 5061 } else { 5060 })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn user_host_port_params() {
        let u = SipUri::parse("sip:alice@atlanta.example.com:5070;transport=tcp;lr").unwrap();
        assert_eq!(u.user.as_deref(), Some("alice"));
        assert_eq!(u.host, "atlanta.example.com");
        assert_eq!(u.port, Some(5070));
        assert_eq!(u.param("transport"), Some(Some("tcp")));
        assert_eq!(u.param("lr"), Some(None));
    }

    #[test]
    fn sips_default_port() {
        let u = SipUri::parse("sips:registrar.example.net").unwrap();
        assert!(u.secure);
        assert_eq!(u.effective_port(), 5061);
    }

    #[test]
    fn ipv6_reference() {
        let u = SipUri::parse("sip:bob@[2001:db8::10]:5062").unwrap();
        assert_eq!(u.host, "[2001:db8::10]");
        assert_eq!(u.port, Some(5062));
    }

    #[test]
    fn rejects_other_schemes() {
        assert_eq!(SipUri::parse("tel:+4930123456"), Err(ParseError::InvalidUri));
    }
}
