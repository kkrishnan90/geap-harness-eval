//! Dialog identification (RFC 3261 §12): Call-ID + local tag + remote tag.

use crate::error::ParseError;
use crate::message::SipMessage;

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct DialogId {
    pub call_id: String,
    pub local_tag: String,
    pub remote_tag: String,
}

/// Dialog id as seen by the UAS side (we are the To side): local = To tag, remote = From tag.
pub fn uas_dialog_id(msg: &SipMessage) -> Result<Option<DialogId>, ParseError> {
    let call_id = msg.call_id()?.to_string();
    match (msg.to_tag(), msg.from_tag()) {
        (Some(local), Some(remote)) => Ok(Some(DialogId { call_id, local_tag: local, remote_tag: remote })),
        _ => Ok(None),
    }
}

/// Dialog id as seen by the UAC side: local = From tag, remote = To tag.
pub fn uac_dialog_id(msg: &SipMessage) -> Result<Option<DialogId>, ParseError> {
    let call_id = msg.call_id()?.to_string();
    match (msg.from_tag(), msg.to_tag()) {
        (Some(local), Some(remote)) => Ok(Some(DialogId { call_id, local_tag: local, remote_tag: remote })),
        _ => Ok(None),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parse;

    #[test]
    fn early_request_has_no_dialog() {
        let m = parse(b"INVITE sip:b@example.com SIP/2.0\r\nCall-ID: x1\r\nFrom: <sip:a@example.com>;tag=aa\r\nTo: <sip:b@example.com>\r\n\r\n").unwrap();
        assert_eq!(uas_dialog_id(&m).unwrap(), None);
    }

    #[test]
    fn sides_are_mirrored() {
        let m = parse(b"BYE sip:b@example.com SIP/2.0\r\ni: x2\r\nf: <sip:a@example.com>;tag=aa\r\nt: <sip:b@example.com>;tag=bb\r\n\r\n").unwrap();
        let uas = uas_dialog_id(&m).unwrap().unwrap();
        let uac = uac_dialog_id(&m).unwrap().unwrap();
        assert_eq!(uas.local_tag, "bb");
        assert_eq!(uac.local_tag, "aa");
        assert_eq!(uas.call_id, "x2");
    }
}
