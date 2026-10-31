use sipcore::{parse, parse_with_limits, Limits, ParseError, SipUri};

fn req(headers: &str, body: &[u8]) -> Vec<u8> {
    let mut v = format!("OPTIONS sip:edge.example.com SIP/2.0\r\n{}\r\n", headers).into_bytes();
    v.extend_from_slice(body);
    v
}

#[test]
fn non_utf8_header_section() {
    let mut m = b"OPTIONS sip:edge.example.com SIP/2.0\r\nSubject: caf".to_vec();
    m.extend_from_slice(&[0xC3, 0x28]);
    m.extend_from_slice(b"\r\nl: 0\r\n\r\n");
    assert_eq!(parse(&m), Err(ParseError::InvalidUtf8));
}

#[test]
fn content_length_too_large_for_limits() {
    assert_eq!(parse(&req("Content-Length: 4294967296000\r\n", b"x")), Err(ParseError::BodyTooLarge));
    assert_eq!(parse(&req("l: 65537\r\n", b"x")), Err(ParseError::BodyTooLarge));
}

#[test]
fn content_length_overflow_and_garbage() {
    for cl in ["99999999999999999999999", "-1", "+5", "1e3", "12 34", "", "0x10", "５"] {
        assert_eq!(
            parse(&req(&format!("Content-Length: {}\r\n", cl), b"")),
            Err(ParseError::InvalidContentLength),
            "Content-Length {:?}",
            cl
        );
    }
}

#[test]
fn conflicting_content_lengths() {
    assert_eq!(parse(&req("Content-Length: 3\r\nl: 4\r\n", b"abcd")), Err(ParseError::InvalidContentLength));
}

#[test]
fn body_shorter_than_content_length() {
    assert_eq!(parse(&req("Content-Length: 10\r\n", b"abc")), Err(ParseError::BodyLengthMismatch));
}

#[test]
fn body_without_content_length_over_limit() {
    let body = vec![b'a'; 65537];
    assert_eq!(parse(&req("Event: x\r\n", &body)), Err(ParseError::BodyTooLarge));
}

#[test]
fn too_many_headers() {
    let mut h = String::new();
    for i in 0..65 {
        h.push_str(&format!("X-Hop-{}: {}\r\n", i, i));
    }
    assert_eq!(parse(&req(&h, b"")), Err(ParseError::TooManyHeaders));
    let small = Limits { max_headers: 3, ..Limits::default() };
    assert_eq!(parse_with_limits(&req("A: 1\r\nB: 2\r\nC: 3\r\nD: 4\r\n", b""), &small), Err(ParseError::TooManyHeaders));
}

#[test]
fn overlong_header_line() {
    let h = format!("Subject: {}\r\n", "x".repeat(5000));
    assert_eq!(parse(&req(&h, b"")), Err(ParseError::HeaderTooLong));
}

#[test]
fn overlong_folded_header() {
    let mut h = String::from("Subject: start\r\n");
    for _ in 0..200 {
        h.push_str(&format!(" {}\r\n", "y".repeat(60)));
    }
    assert_eq!(parse(&req(&h, b"")), Err(ParseError::HeaderTooLong));
}

#[test]
fn overlong_start_line() {
    let m = format!("OPTIONS sip:{}@edge.example.com SIP/2.0\r\n\r\n", "u".repeat(5000));
    assert_eq!(parse(m.as_bytes()), Err(ParseError::HeaderTooLong));
}

#[test]
fn fold_before_any_header() {
    assert_eq!(parse(b"OPTIONS sip:a@b SIP/2.0\r\n  dangling\r\nl: 0\r\n\r\n"), Err(ParseError::MalformedHeader { line: 2 }));
}

#[test]
fn invalid_header_names() {
    assert_eq!(parse(&req("Via: x\r\nBad Name: x\r\n", b"")), Err(ParseError::MalformedHeader { line: 3 }));
    assert_eq!(parse(&req(": novalue\r\n", b"")), Err(ParseError::MalformedHeader { line: 2 }));
    assert_eq!(parse(&req("X-Ünicode: 1\r\n", b"")), Err(ParseError::MalformedHeader { line: 2 }));
}

#[test]
fn bare_lf_inside_header_section() {
    assert_eq!(parse(&req("Via: a\nInjected: 1\r\n", b"")), Err(ParseError::MalformedHeader { line: 2 }));
}

#[test]
fn bad_status_codes() {
    for line in ["SIP/2.0 99 Weird", "SIP/2.0 700 Weird", "SIP/2.0 2000 OK", "SIP/2.0 +20 OK", "SIP/2.0 OK"] {
        assert_eq!(parse(format!("{}\r\n\r\n", line).as_bytes()), Err(ParseError::InvalidStartLine), "{}", line);
    }
}

#[test]
fn bad_methods() {
    assert_eq!(parse(b" sip:a@b SIP/2.0\r\n\r\n"), Err(ParseError::InvalidStartLine));
    assert_eq!(parse(b"INV<ITE sip:a@b SIP/2.0\r\n\r\n"), Err(ParseError::InvalidStartLine));
}

#[test]
fn bad_uris() {
    for u in [
        "sip:", "sip:@example.com", "sip:alice@", "sip:alice@example.com:99999", "sip:alice@example.com:",
        "sip:alice@example.com:50a0", "sip:bob@[2001:db8::1", "sip:bob@[]:5060", "sip:bob@[2001:db8::1]x",
        "sip:alice@exa mple.com", "sip:alice@example.com;;lr", "sip:alice@example.com;", "sip:a@b:0",
    ] {
        assert_eq!(SipUri::parse(u), Err(ParseError::InvalidUri), "{}", u);
    }
    assert_eq!(parse(b"INVITE sip:bob@[2001:db8::1 SIP/2.0\r\n\r\n"), Err(ParseError::InvalidUri));
}

#[test]
fn cseq_errors() {
    for v in ["99999999999 INVITE", "2147483648 OPTIONS", "-1 OPTIONS", "1", "OPTIONS", "1 OPTIONS extra", "1 OPT<IONS", ""] {
        let m = parse(&req(&format!("CSeq: {}\r\n", v), b"")).unwrap();
        assert_eq!(m.cseq(), Err(ParseError::InvalidCSeq), "CSeq {:?}", v);
    }
    let m = parse(&req("CSeq: 7 INVITE\r\n", b"")).unwrap();
    assert_eq!(m.cseq(), Err(ParseError::InvalidCSeq), "method mismatch");
    let ok = parse(&req("CSeq: 2147483647 OPTIONS\r\n", b"")).unwrap();
    assert_eq!(ok.cseq().unwrap().seq, 2147483647);
}

#[test]
fn max_forwards_errors() {
    for v in ["256", "-1", "70a", "", "1000"] {
        let m = parse(&req(&format!("Max-Forwards: {}\r\n", v), b"")).unwrap();
        assert_eq!(m.max_forwards(), Err(ParseError::InvalidMaxForwards), "Max-Forwards {:?}", v);
    }
    let m = parse(&req("Max-Forwards: 0\r\n", b"")).unwrap();
    assert_eq!(m.max_forwards(), Ok(Some(0)));
    let m = parse(&req("Via: x\r\n", b"")).unwrap();
    assert_eq!(m.max_forwards(), Ok(None));
}

#[test]
fn custom_limits_respected() {
    let tight = Limits { max_headers: 64, max_line_len: 40, max_body: 4 };
    assert_eq!(parse_with_limits(&req("Subject: this header is definitely too long\r\n", b""), &tight), Err(ParseError::HeaderTooLong));
    assert_eq!(parse_with_limits(&req("l: 5\r\n", b"hello"), &tight), Err(ParseError::BodyTooLarge));
    assert!(parse_with_limits(&req("l: 4\r\n", b"hell"), &tight).is_ok());
}
