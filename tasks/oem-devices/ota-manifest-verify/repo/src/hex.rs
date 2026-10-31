//! Hex helpers (lower-case output, case-insensitive input).

pub fn encode(bytes: &[u8]) -> String {
    const DIGITS: &[u8; 16] = b"0123456789abcdef";
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push(DIGITS[(b >> 4) as usize] as char);
        s.push(DIGITS[(b & 0x0f) as usize] as char);
    }
    s
}

fn nibble(c: u8) -> Option<u8> {
    match c {
        b'0'..=b'9' => Some(c - b'0'),
        b'a'..=b'f' => Some(c - b'a' + 10),
        b'A'..=b'F' => Some(c - b'A' + 10),
        _ => None,
    }
}

/// Decode exactly `N` bytes from `2 * N` hex characters.
pub fn decode_fixed<const N: usize>(s: &str) -> Option<[u8; N]> {
    let b = s.as_bytes();
    if b.len() != 2 * N {
        return None;
    }
    let mut out = [0u8; N];
    for i in 0..N {
        out[i] = (nibble(b[2 * i])? << 4) | nibble(b[2 * i + 1])?;
    }
    Some(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip() {
        let bytes = [0x00u8, 0x7f, 0x80, 0xff];
        assert_eq!(encode(&bytes), "007f80ff");
        assert_eq!(decode_fixed::<4>("007F80ff"), Some(bytes));
    }

    #[test]
    fn rejects_bad_input() {
        assert_eq!(decode_fixed::<2>("abc"), None);
        assert_eq!(decode_fixed::<2>("abcg"), None);
        assert_eq!(decode_fixed::<1>("+1"), None);
    }
}
