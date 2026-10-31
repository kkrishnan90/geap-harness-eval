use sipcore::dialog::{uac_dialog_id, uas_dialog_id};
use sipcore::parse;
use sipcore::transaction::server_key;

const BYE: &[u8] = b"BYE sip:alice@pc33.atlanta.example.com SIP/2.0\r\n\
Via: SIP/2.0/TCP 192.0.2.4;branch=z9hG4bKnashd92\r\n\
Max-Forwards: 70\r\n\
From: Bob <sip:bob@biloxi.example.com>;tag=a6c85cf\r\n\
To: Alice <sip:alice@atlanta.example.com>;tag=1928301774\r\n\
Call-ID: a84b4c76e66710\r\n\
CSeq: 231 BYE\r\n\
Content-Length: 0\r\n\r\n";

#[test]
fn bye_dialog_ids() {
    let m = parse(BYE).unwrap();
    let uas = uas_dialog_id(&m).unwrap().unwrap();
    assert_eq!(uas.local_tag, "1928301774");
    assert_eq!(uas.remote_tag, "a6c85cf");
    assert_eq!(uac_dialog_id(&m).unwrap().unwrap().local_tag, "a6c85cf");
}

#[test]
fn bye_transaction_key() {
    let k = server_key(&parse(BYE).unwrap()).unwrap().unwrap();
    assert_eq!(k.branch, "z9hG4bKnashd92");
    assert_eq!(k.sent_by, "192.0.2.4");
    assert_eq!(k.method, "BYE");
}

#[test]
fn response_has_no_server_key() {
    let m = parse(b"SIP/2.0 200 OK\r\nVia: SIP/2.0/UDP h;branch=z9hG4bKx\r\nl: 0\r\n\r\n").unwrap();
    assert_eq!(server_key(&m).unwrap(), None);
}

#[test]
fn missing_call_id_reported() {
    let m = parse(b"BYE sip:a@b SIP/2.0\r\nf: <sip:x@y>;tag=1\r\nt: <sip:a@b>;tag=2\r\n\r\n").unwrap();
    assert!(uas_dialog_id(&m).is_err());
}
