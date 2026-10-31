//! Parsed SIP message.

use crate::uri::SipUri;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Method {
    Invite,
    Ack,
    Bye,
    Cancel,
    Register,
    Options,
    Info,
    Update,
    Prack,
    Subscribe,
    Notify,
    Refer,
    Message,
    /// Extension method (token).
    Other(String),
}

impl Method {
    pub fn from_token(s: &str) -> Method {
        match s {
            "INVITE" => Method::Invite,
            "ACK" => Method::Ack,
            "BYE" => Method::Bye,
            "CANCEL" => Method::Cancel,
            "REGISTER" => Method::Register,
            "OPTIONS" => Method::Options,
            "INFO" => Method::Info,
            "UPDATE" => Method::Update,
            "PRACK" => Method::Prack,
            "SUBSCRIBE" => Method::Subscribe,
            "NOTIFY" => Method::Notify,
            "REFER" => Method::Refer,
            "MESSAGE" => Method::Message,
            other => Method::Other(other.to_string()),
        }
    }

    pub fn as_str(&self) -> &str {
        match self {
            Method::Invite => "INVITE",
            Method::Ack => "ACK",
            Method::Bye => "BYE",
            Method::Cancel => "CANCEL",
            Method::Register => "REGISTER",
            Method::Options => "OPTIONS",
            Method::Info => "INFO",
            Method::Update => "UPDATE",
            Method::Prack => "PRACK",
            Method::Subscribe => "SUBSCRIBE",
            Method::Notify => "NOTIFY",
            Method::Refer => "REFER",
            Method::Message => "MESSAGE",
            Method::Other(s) => s,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum StartLine {
    Request { method: Method, uri: SipUri },
    Response { code: u16, reason: String },
}

/// A parsed message. Header names keep their wire spelling; lookups are
/// case-insensitive and understand compact forms.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SipMessage {
    pub start: StartLine,
    pub headers: Vec<(String, String)>,
    pub body: Vec<u8>,
}

/// Map compact header names to their long form (lower case).
pub fn canonical_name(name: &str) -> String {
    let lower = name.to_ascii_lowercase();
    match lower.as_str() {
        "v" => "via".into(),
        "f" => "from".into(),
        "t" => "to".into(),
        "i" => "call-id".into(),
        "l" => "content-length".into(),
        "m" => "contact".into(),
        "c" => "content-type".into(),
        _ => lower,
    }
}

impl SipMessage {
    pub fn is_request(&self) -> bool {
        matches!(self.start, StartLine::Request { .. })
    }

    pub fn method(&self) -> Option<&Method> {
        match &self.start {
            StartLine::Request { method, .. } => Some(method),
            StartLine::Response { .. } => None,
        }
    }

    /// First value of the named header (case-insensitive, compact forms understood).
    pub fn header(&self, name: &str) -> Option<&str> {
        let want = canonical_name(name);
        self.headers.iter().find(|(n, _)| canonical_name(n) == want).map(|(_, v)| v.as_str())
    }

    /// All values of the named header, in order.
    pub fn header_all(&self, name: &str) -> Vec<&str> {
        let want = canonical_name(name);
        self.headers.iter().filter(|(n, _)| canonical_name(n) == want).map(|(_, v)| v.as_str()).collect()
    }
}
