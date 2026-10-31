use sipcore::{parse, Method, StartLine};

const INVITE: &[u8] = b"INVITE sip:bob@biloxi.example.com SIP/2.0\r\n\
Via: SIP/2.0/UDP pc33.atlanta.example.com;branch=z9hG4bK776asdhds\r\n\
Max-Forwards: 70\r\n\
To: Bob <sip:bob@biloxi.example.com>\r\n\
From: Alice <sip:alice@atlanta.example.com>;tag=1928301774\r\n\
Call-ID: a84b4c76e66710@pc33.atlanta.example.com\r\n\
CSeq: 314159 INVITE\r\n\
Contact: <sip:alice@pc33.atlanta.example.com>\r\n\
Content-Type: application/sdp\r\n\
Content-Length: 31\r\n\
\r\n\
v=0\r\no=alice 2890844526 0 IN IP4\r\n";

#[test]
fn invite_with_sdp_body() {
    let m = parse(INVITE).unwrap();
    match &m.start {
        StartLine::Request { method, uri } => {
            assert_eq!(*method, Method::Invite);
            assert_eq!(uri.user.as_deref(), Some("bob"));
            assert_eq!(uri.host, "biloxi.example.com");
        }
        other => panic!("unexpected {:?}", other),
    }
    assert_eq!(m.headers.len(), 9);
    assert_eq!(m.header("content-type"), Some("application/sdp"));
    assert_eq!(m.body.len(), 31);
    assert!(m.body.starts_with(b"v=0\r\n"));
    assert_eq!(m.cseq().unwrap().seq, 314159);
}

#[test]
fn compact_forms() {
    let m = parse(b"MESSAGE sip:user2@domain.example SIP/2.0\r\nv: SIP/2.0/TCP h1;branch=z9hG4bK1\r\ni: abc@h1\r\nf: <sip:u1@d>;tag=9\r\nt: <sip:user2@domain.example>\r\nl: 5\r\nc: text/plain\r\n\r\nhello").unwrap();
    assert_eq!(m.call_id().unwrap(), "abc@h1");
    assert_eq!(m.header("Content-Type"), Some("text/plain"));
    assert_eq!(m.body, b"hello");
}

#[test]
fn response_with_reason_spaces() {
    let m = parse(b"SIP/2.0 486 Busy Here\r\nCSeq: 1 INVITE\r\nl: 0\r\n\r\n").unwrap();
    assert_eq!(m.start, StartLine::Response { code: 486, reason: "Busy Here".into() });
    assert!(!m.is_request());
}

#[test]
fn body_without_content_length_takes_rest() {
    let m = parse(b"NOTIFY sip:a@b SIP/2.0\r\nEvent: dialog\r\n\r\n<xml/>").unwrap();
    assert_eq!(m.body, b"<xml/>");
}

#[test]
fn folded_header_is_unfolded() {
    let m = parse(b"OPTIONS sip:a@b SIP/2.0\r\nSubject: I know you're there,\r\n  pick up the phone\r\n\tand talk to me!\r\nl: 0\r\n\r\n").unwrap();
    assert_eq!(m.header("subject"), Some("I know you're there, pick up the phone and talk to me!"));
}

#[test]
fn repeated_headers_in_order() {
    let m = parse(b"OPTIONS sip:a@b SIP/2.0\r\nRoute: <sip:p1;lr>\r\nRoute: <sip:p2;lr>\r\nl: 0\r\n\r\n").unwrap();
    assert_eq!(m.header_all("route"), vec!["<sip:p1;lr>", "<sip:p2;lr>"]);
}

#[test]
fn extension_method() {
    let m = parse(b"PUBLISH sip:presentity@example.com SIP/2.0\r\nl: 0\r\n\r\n").unwrap();
    assert_eq!(m.method(), Some(&Method::Other("PUBLISH".into())));
}
