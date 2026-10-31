use ota_agent::hex;
use ota_agent::sha256::digest;
use ota_agent::{parse_manifest, ManifestError, Version};

fn image(len: usize) -> Vec<u8> {
    (0..len as u32).map(|i| (i.wrapping_mul(2654435761) >> 13) as u8).collect()
}

fn v2_text(img: &[u8], chunk_size: usize, version: &str, security_version: u32) -> String {
    let mut s = format!(
        "format = 2\ncomponent = tcu-main\nversion = {version}\nsecurity_version = {security_version}\n\
         image_size = {}\nchunk_size = {chunk_size}\nimage_sha256 = {}\n",
        img.len(),
        hex::encode(&digest(img))
    );
    for (i, c) in img.chunks(chunk_size).enumerate() {
        s.push_str(&format!("chunk.{i} = {}\n", hex::encode(&digest(c))));
    }
    s
}

#[test]
fn parses_v2_fields() {
    let img = image(10_000);
    let m = parse_manifest(&v2_text(&img, 4096, "6.0.0", 7)).unwrap();
    assert_eq!(m.format, 2);
    assert_eq!(m.version, Version::new(6, 0, 0));
    assert_eq!(m.security_version, 7);
    assert_eq!(m.chunk_size, 4096);
    assert_eq!(m.chunk_sha256.len(), 3);
    assert_eq!(m.chunk_sha256[0], digest(&img[..4096]));
    assert_eq!(m.chunk_sha256[2], digest(&img[8192..]));
}

#[test]
fn chunk_order_in_file_does_not_matter() {
    let img = image(9000);
    let text = v2_text(&img, 3000, "6.0.0", 1);
    let mut lines: Vec<&str> = text.lines().collect();
    lines.reverse();
    let m = parse_manifest(&lines.join("\n")).unwrap();
    assert_eq!(m.chunk_sha256, vec![digest(&img[..3000]), digest(&img[3000..6000]), digest(&img[6000..])]);
}

#[test]
fn exact_multiple_of_chunk_size() {
    let img = image(8192);
    let m = parse_manifest(&v2_text(&img, 4096, "6.0.0", 1)).unwrap();
    assert_eq!(m.chunk_sha256.len(), 2);
}

#[test]
fn format1_defaults() {
    let img = image(100);
    let text = format!(
        "format = 1\ncomponent = tcu-main\nversion = 5.3.1\nimage_size = 100\nimage_sha256 = {}\n",
        hex::encode(&digest(&img))
    );
    let m = parse_manifest(&text).unwrap();
    assert_eq!(m.security_version, 0);
    assert_eq!(m.chunk_size, 0);
    assert!(m.chunk_sha256.is_empty());
}

#[test]
fn v2_requires_security_version_and_chunk_size() {
    let img = image(5000);
    let text = v2_text(&img, 4096, "6.0.0", 3);
    assert_eq!(
        parse_manifest(&text.replace("security_version = 3\n", "")),
        Err(ManifestError::MissingKey("security_version".into()))
    );
    assert_eq!(
        parse_manifest(&text.replace("chunk_size = 4096\n", "")),
        Err(ManifestError::MissingKey("chunk_size".into()))
    );
}

#[test]
fn v2_invalid_values() {
    let img = image(5000);
    let text = v2_text(&img, 4096, "6.0.0", 3);
    assert!(matches!(
        parse_manifest(&text.replace("chunk_size = 4096", "chunk_size = 0")),
        Err(ManifestError::InvalidValue { key, .. }) if key == "chunk_size"
    ));
    assert!(matches!(
        parse_manifest(&text.replace("security_version = 3", "security_version = 4294967296")),
        Err(ManifestError::InvalidValue { key, .. }) if key == "security_version"
    ));
    assert!(matches!(
        parse_manifest(&text.replace("security_version = 3", "security_version = -3")),
        Err(ManifestError::InvalidValue { key, .. }) if key == "security_version"
    ));
    let bad_digest = text.replacen("chunk.1 = ", "chunk.1 = zz", 1);
    assert!(matches!(
        parse_manifest(&bad_digest),
        Err(ManifestError::InvalidValue { key, .. }) if key == "chunk.1"
    ));
}

#[test]
fn chunk_count_mismatch() {
    let img = image(10_000);
    let text = v2_text(&img, 4096, "6.0.0", 3);
    let missing_last: String = text.lines().filter(|l| !l.starts_with("chunk.2")).map(|l| format!("{l}\n")).collect();
    assert_eq!(parse_manifest(&missing_last), Err(ManifestError::ChunkCountMismatch { expected: 3, found: 2 }));
    let extra = format!("{text}chunk.3 = {}\n", hex::encode(&digest(b"x")));
    assert_eq!(parse_manifest(&extra), Err(ManifestError::ChunkCountMismatch { expected: 3, found: 4 }));
}

#[test]
fn gap_in_chunk_indices() {
    let img = image(10_000);
    let text = v2_text(&img, 4096, "6.0.0", 3).replace("chunk.1 =", "chunk.7 =");
    assert_eq!(parse_manifest(&text), Err(ManifestError::MissingChunk(1)));
}

#[test]
fn duplicate_chunk_key() {
    let img = image(5000);
    let text = format!("{}chunk.0 = {}\n", v2_text(&img, 4096, "6.0.0", 3), hex::encode(&digest(b"x")));
    assert_eq!(parse_manifest(&text), Err(ManifestError::DuplicateKey("chunk.0".into())));
}

#[test]
fn version_ordering_is_numeric() {
    assert!(Version::new(4, 10, 0) > Version::new(4, 9, 0));
    assert!(Version::new(10, 0, 0) > Version::new(9, 99, 99));
    assert!(Version::new(1, 2, 10) > Version::new(1, 2, 9));
    assert!(Version::new(1, 2, 3) == Version::new(1, 2, 3));
}

#[test]
fn unsupported_format_still_rejected() {
    let img = image(5000);
    let text = v2_text(&img, 4096, "6.0.0", 3).replace("format = 2", "format = 3");
    assert_eq!(parse_manifest(&text), Err(ManifestError::UnsupportedFormat(3)));
}
