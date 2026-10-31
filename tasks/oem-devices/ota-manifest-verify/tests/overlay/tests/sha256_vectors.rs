use ota_agent::hex;
use ota_agent::sha256::{ct_eq, digest, Sha256};

fn h(data: &[u8]) -> String {
    hex::encode(&digest(data))
}

#[test]
fn nist_short_vectors() {
    assert_eq!(h(b""), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    assert_eq!(h(b"abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    assert_eq!(
        h(b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"),
        "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"
    );
}

#[test]
fn million_a() {
    let data = vec![b'a'; 1_000_000];
    assert_eq!(h(&data), "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0");
}

#[test]
fn streaming_matches_one_shot() {
    let data: Vec<u8> = (0..10_000u32).map(|i| (i * 31 % 251) as u8).collect();
    for split in [1usize, 55, 56, 63, 64, 65, 4096] {
        let mut s = Sha256::new();
        for c in data.chunks(split) {
            s.update(c);
        }
        assert_eq!(s.finalize(), digest(&data), "split {split}");
    }
}

#[test]
fn constant_time_compare() {
    let a = digest(b"x");
    let mut b = a;
    assert!(ct_eq(&a, &b));
    b[31] ^= 1;
    assert!(!ct_eq(&a, &b));
}
