//! Valid-but-unusual traffic that must keep working after hardening.
use sipcore::{parse, parse_with_limits, Limits, SipUri, StartLine};

fn req(headers: &str, body: &[u8]) -> Vec<u8> {
    let mut v = format!("OPTIONS sip:edge.example.com SIP/2.0\r\n{}\r\n", headers).into_bytes();
    v.extend_from_slice(body);
    v
}

#[test]
fn trailing_bytes_after_body_discarded() {
    let m = parse(&req("Content-Length: 3\r\n", b"abcGARBAGE")).unwrap();
    assert_eq!(m.body, b"abc");
}

#[test]
fn binary_body_allowed() {
    let body = [0u8, 0xff, 0xc3, 0x28, b'\r', b'\n'];
    let m = parse(&req("Content-Type: application/octet-stream\r\nl: 6\r\n", &body)).unwrap();
    assert_eq!(m.body, body);
}

#[test]
fn exactly_max_headers_allowed() {
    let mut h = String::new();
    for i in 0..64 {
        h.push_str(&format!("X-Hop-{}: {}\r\n", i, i));
    }
    assert_eq!(parse(&req(&h, b"")).unwrap().headers.len(), 64);
}

#[test]
fn repeated_identical_content_length() {
    let m = parse(&req("Content-Length: 2\r\nl: 2\r\n", b"ok")).unwrap();
    assert_eq!(m.body, b"ok");
}

#[test]
fn long_but_legal_header() {
    let h = format!("P-Asserted-Identity: <sip:{}@example.com>\r\n", "9".repeat(3900));
    assert!(parse(&req(&h, b"")).is_ok());
}

#[test]
fn larger_limits_allow_more() {
    let big = Limits { max_headers: 200, max_line_len: 20_000, max_body: 1 << 20 };
    let h = format!("Subject: {}\r\n", "x".repeat(10_000));
    assert!(parse_with_limits(&req(&h, &vec![b'b'; 100_000]), &big).is_ok());
}

#[test]
fn content_length_zero_and_whitespace() {
    let m = parse(&req("Content-Length:   0  \r\n", b"")).unwrap();
    assert!(m.body.is_empty());
}

#[test]
fn ipv6_and_params_uri() {
    let u = SipUri::parse("sips:bob@[2001:db8::10]:5061;transport=tls;lr").unwrap();
    assert_eq!(u.host, "[2001:db8::10]");
    assert_eq!(u.port, Some(5061));
    let u = SipUri::parse("sip:+4930123456@gw-1.example.net;user=phone").unwrap();
    assert_eq!(u.host, "gw-1.example.net");
}

#[test]
fn user_with_password_and_dots() {
    let u = SipUri::parse("sip:alice:secret@atlanta.example.com").unwrap();
    assert_eq!(u.user.as_deref(), Some("alice:secret"));
}

#[test]
fn utf8_in_header_values_ok() {
    let m = parse(&req("Subject: Café Zürich ☎\r\n", b"")).unwrap();
    assert_eq!(m.header("subject"), Some("Café Zürich ☎"));
}

#[test]
fn response_without_reason_phrase() {
    let m = parse(b"SIP/2.0 100 \r\n\r\n").unwrap();
    assert_eq!(m.start, StartLine::Response { code: 100, reason: "".into() });
}
