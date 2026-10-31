//! Deterministic mutation fuzzing: nothing on the receive path may panic.
use std::panic::{self, AssertUnwindSafe};

use sipcore::dialog::{uac_dialog_id, uas_dialog_id};
use sipcore::transaction::server_key;
use sipcore::{parse, parse_with_limits, Limits, SipUri};

struct XorShift(u64);

impl XorShift {
    fn next(&mut self) -> u64 {
        let mut x = self.0;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.0 = x;
        x
    }
    fn below(&mut self, n: usize) -> usize {
        (self.next() % n as u64) as usize
    }
}

const SEEDS: &[&[u8]] = &[
    b"INVITE sip:bob@biloxi.example.com:5062;transport=tcp SIP/2.0\r\nVia: SIP/2.0/UDP pc33.atlanta.example.com;branch=z9hG4bK776asdhds\r\nMax-Forwards: 70\r\nTo: Bob <sip:bob@biloxi.example.com>\r\nFrom: Alice <sip:alice@atlanta.example.com>;tag=1928301774\r\nCall-ID: a84b4c76e66710\r\nCSeq: 314159 INVITE\r\nContent-Length: 4\r\n\r\nv=0\n",
    b"SIP/2.0 180 Ringing\r\nv: SIP/2.0/UDP h;branch=z9hG4bKx\r\nf: <sip:a@b>;tag=1\r\nt: <sip:c@d>;tag=2\r\ni: id\r\nCSeq: 1 INVITE\r\nl: 0\r\n\r\n",
    b"REGISTER sips:registrar.example.com SIP/2.0\r\nVia: SIP/2.0/TLS [2001:db8::9]:5061;branch=z9hG4bKr\r\nContact: <sips:u@[2001:db8::9]:5061>\r\nSubject: folded\r\n value here\r\nCSeq: 2 REGISTER\r\n\r\n",
];

const INTERESTING: &[&[u8]] = &[
    b"\r\n", b"\r", b"\n", b":", b" ", b"\t", b"[", b"]", b"@", b";", b"=", b"99999999999999999999",
    b"4294967296", b"-", b"\xff", b"\xc3", b"Content-Length: ", b"l: 9999999", b"CSeq: ", b"Max-Forwards: 999",
    b"sip:", b"\x00", b"SIP/2.0 ",
];

fn mutate(rng: &mut XorShift, input: &[u8]) -> Vec<u8> {
    let mut v = input.to_vec();
    for _ in 0..1 + rng.below(4) {
        match rng.below(6) {
            0 if !v.is_empty() => {
                let i = rng.below(v.len());
                v[i] = rng.next() as u8;
            }
            1 if !v.is_empty() => {
                let i = rng.below(v.len());
                v.truncate(i);
            }
            2 => {
                let i = rng.below(v.len() + 1);
                let ins = INTERESTING[rng.below(INTERESTING.len())];
                v.splice(i..i, ins.iter().copied());
            }
            3 if v.len() > 2 => {
                let a = rng.below(v.len());
                let b = (a + 1 + rng.below(16)).min(v.len());
                v.drain(a..b);
            }
            4 if !v.is_empty() => {
                let a = rng.below(v.len());
                let b = (a + 1 + rng.below(32)).min(v.len());
                let chunk: Vec<u8> = v[a..b].to_vec();
                let at = rng.below(v.len() + 1);
                v.splice(at..at, chunk);
            }
            _ => v.extend_from_slice(b"\r\n\r\n"),
        }
    }
    v
}

fn exercise(bytes: &[u8]) {
    let limits = Limits { max_headers: 8, max_line_len: 128, max_body: 64 };
    for res in [parse(bytes), parse_with_limits(bytes, &limits)] {
        if let Ok(m) = res {
            let _ = m.cseq();
            let _ = m.call_id();
            let _ = m.via_branch();
            let _ = m.from_tag();
            let _ = m.to_tag();
            let _ = m.max_forwards();
            let _ = uas_dialog_id(&m);
            let _ = uac_dialog_id(&m);
            let _ = server_key(&m);
            for (_, v) in &m.headers {
                let _ = SipUri::parse(v);
            }
        }
    }
    if let Ok(s) = std::str::from_utf8(bytes) {
        let _ = SipUri::parse(s);
        let _ = SipUri::parse(s.trim());
    }
}

#[test]
fn mutated_messages_never_panic() {
    let prev = panic::take_hook();
    panic::set_hook(Box::new(|_| {}));
    let mut rng = XorShift(0x5EED_5100_2026_0001);
    let mut panics = 0usize;
    let mut first: Option<Vec<u8>> = None;
    for i in 0..20_000 {
        let seed = SEEDS[i % SEEDS.len()];
        let input = mutate(&mut rng, seed);
        if panic::catch_unwind(AssertUnwindSafe(|| exercise(&input))).is_err() {
            panics += 1;
            if first.is_none() {
                first = Some(input);
            }
        }
    }
    panic::set_hook(prev);
    assert_eq!(panics, 0, "{} inputs panicked; first: {:?}", panics, first.map(|v| String::from_utf8_lossy(&v).into_owned()));
}

#[test]
fn hostile_uris_never_panic() {
    let prev = panic::take_hook();
    panic::set_hook(Box::new(|_| {}));
    let alphabet = b"sip:@[]:;=.-0123456789abAZ%\xc3\xa9 ";
    let mut rng = XorShift(0xC0FF_EE00_1234_5678);
    let mut panics = 0;
    for _ in 0..20_000 {
        let len = rng.below(24);
        let mut s: Vec<u8> = b"sip:".to_vec();
        for _ in 0..len {
            s.push(alphabet[rng.below(alphabet.len())]);
        }
        let s = String::from_utf8_lossy(&s).into_owned();
        if panic::catch_unwind(|| {
            let _ = SipUri::parse(&s);
        })
        .is_err()
        {
            panics += 1;
        }
    }
    panic::set_hook(prev);
    assert_eq!(panics, 0);
}
