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
            Some(i) => (Some(main[..i].to_string()), &main[i + 1..]),
            None => (None, main),
        };

        let (host, port) = if hostport.starts_with('[') {
            let end = hostport.find(']').unwrap();
            let host = &hostport[..=end];
            let port = if hostport.len() > end + 1 {
                Some(hostport[end + 2..].parse::<u16>().unwrap())
            } else {
                None
            };
            (host, port)
        } else {
            match hostport.rfind(':') {
                Some(i) => (&hostport[..i], Some(hostport[i + 1..].parse::<u16>().unwrap())),
                None => (hostport, None),
            }
        };

        let mut params = Vec::new();
        if let Some(ps) = params_str {
            for p in ps.split(';') {
                match p.find('=') {
                    Some(i) => params.push((p[..i].to_string(), Some(p[i + 1..].to_string()))),
                    None => params.push((p.to_string(), None)),
                }
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
