use ota_agent::hex;
use ota_agent::sha256::digest;
use ota_agent::{parse_manifest, verify_update, DeviceState, Manifest, Version, VerifyError};

fn image(len: usize) -> Vec<u8> {
    (0..len as u32).map(|i| (i.wrapping_mul(40503) >> 7) as u8).collect()
}

fn v2(img: &[u8], chunk_size: usize, version: &str, security_version: u32) -> Manifest {
    let mut s = format!(
        "format = 2\ncomponent = tcu-main\nversion = {version}\nsecurity_version = {security_version}\n\
         image_size = {}\nchunk_size = {chunk_size}\nimage_sha256 = {}\n",
        img.len(),
        hex::encode(&digest(img))
    );
    for (i, c) in img.chunks(chunk_size).enumerate() {
        s.push_str(&format!("chunk.{i} = {}\n", hex::encode(&digest(c))));
    }
    parse_manifest(&s).expect("valid v2 manifest")
}

fn v1(img: &[u8], version: &str) -> Manifest {
    parse_manifest(&format!(
        "format = 1\ncomponent = tcu-main\nversion = {version}\nimage_size = {}\nimage_sha256 = {}\n",
        img.len(),
        hex::encode(&digest(img))
    ))
    .expect("valid v1 manifest")
}

fn device(installed: Version, floor: u32) -> DeviceState {
    let mut d = DeviceState::new("tcu-main", installed);
    d.security_floor = floor;
    d
}

#[test]
fn device_state_new_has_zero_floor() {
    assert_eq!(DeviceState::new("tcu-main", Version::new(1, 0, 0)).security_floor, 0);
}

#[test]
fn accepts_newer_v2_image() {
    let img = image(10_000);
    let m = v2(&img, 4096, "6.0.0", 7);
    let ok = verify_update(&m, &img, &device(Version::new(5, 9, 2), 7)).unwrap();
    assert_eq!(ok.version, Version::new(6, 0, 0));
    assert_eq!(ok.security_version, 7);
    assert_eq!(ok.chunks_verified, 3);
}

#[test]
fn accepts_numerically_newer_version() {
    let img = image(3000);
    let m = v2(&img, 1024, "4.10.0", 2);
    assert!(verify_update(&m, &img, &device(Version::new(4, 9, 7), 2)).is_ok());
}

#[test]
fn rejects_older_version() {
    let img = image(3000);
    let m = v2(&img, 1024, "4.9.7", 9);
    assert_eq!(
        verify_update(&m, &img, &device(Version::new(4, 10, 0), 2)),
        Err(VerifyError::Rollback { installed: Version::new(4, 10, 0), offered: Version::new(4, 9, 7) })
    );
}

#[test]
fn rejects_same_version() {
    let img = image(3000);
    let m = v2(&img, 1024, "4.10.0", 2);
    assert_eq!(
        verify_update(&m, &img, &device(Version::new(4, 10, 0), 2)),
        Err(VerifyError::AlreadyInstalled(Version::new(4, 10, 0)))
    );
}

#[test]
fn rollback_applies_to_format1() {
    let img = image(500);
    let m = v1(&img, "5.1.0");
    assert!(matches!(
        verify_update(&m, &img, &device(Version::new(5, 2, 0), 0)),
        Err(VerifyError::Rollback { .. })
    ));
    let v1_ok = verify_update(&v1(&img, "5.3.0"), &img, &device(Version::new(5, 2, 0), 0)).unwrap();
    assert_eq!(v1_ok.security_version, 0);
    assert_eq!(v1_ok.chunks_verified, 0);
}

#[test]
fn rejects_security_version_below_floor() {
    let img = image(3000);
    let m = v2(&img, 1024, "7.0.0", 6);
    assert_eq!(
        verify_update(&m, &img, &device(Version::new(6, 0, 0), 7)),
        Err(VerifyError::SecurityVersionTooLow { floor: 7, offered: 6 })
    );
}

#[test]
fn format1_rejected_when_floor_set() {
    let img = image(500);
    assert_eq!(
        verify_update(&v1(&img, "9.0.0"), &img, &device(Version::new(6, 0, 0), 1)),
        Err(VerifyError::SecurityVersionTooLow { floor: 1, offered: 0 })
    );
}

#[test]
fn security_version_above_floor_ok() {
    let img = image(3000);
    let m = v2(&img, 1024, "7.0.0", 12);
    assert!(verify_update(&m, &img, &device(Version::new(6, 0, 0), 7)).is_ok());
}

#[test]
fn reports_first_corrupt_chunk() {
    let img = image(10_000);
    let m = v2(&img, 4096, "6.0.0", 7);
    let mut bad = img.clone();
    bad[5000] ^= 0x01; // chunk 1
    bad[9999] ^= 0x80; // chunk 2
    assert_eq!(
        verify_update(&m, &bad, &device(Version::new(5, 0, 0), 0)),
        Err(VerifyError::ChunkDigestMismatch { index: 1 })
    );
}

#[test]
fn reports_corrupt_short_last_chunk() {
    let img = image(10_000);
    let m = v2(&img, 4096, "6.0.0", 7);
    let mut bad = img.clone();
    bad[8192] ^= 0x10;
    assert_eq!(
        verify_update(&m, &bad, &device(Version::new(5, 0, 0), 0)),
        Err(VerifyError::ChunkDigestMismatch { index: 2 })
    );
}

#[test]
fn chunk_list_from_other_image_detected() {
    // manifest whose image digest matches but chunk digests belong to another build
    let img = image(6000);
    let other: Vec<u8> = img.iter().map(|b| b.wrapping_add(1)).collect();
    let mut m = v2(&img, 2048, "6.0.0", 7);
    m.chunk_sha256[0] = digest(&other[..2048]);
    assert_eq!(
        verify_update(&m, &img, &device(Version::new(5, 0, 0), 0)),
        Err(VerifyError::ChunkDigestMismatch { index: 0 })
    );
}

#[test]
fn image_digest_still_checked() {
    let img = image(6000);
    let mut m = v2(&img, 2048, "6.0.0", 7);
    m.image_sha256[0] ^= 0xff;
    assert_eq!(verify_update(&m, &img, &device(Version::new(5, 0, 0), 0)), Err(VerifyError::ImageDigestMismatch));
}

#[test]
fn check_order() {
    let img = image(6000);
    let m = v2(&img, 2048, "4.0.0", 1);
    // wrong component beats rollback
    let other = DeviceState::new("tcu-modem", Version::new(9, 0, 0));
    assert!(matches!(verify_update(&m, &img, &other), Err(VerifyError::ComponentMismatch { .. })));
    // rollback beats security floor and size
    assert!(matches!(
        verify_update(&m, &img[..10], &device(Version::new(5, 0, 0), 3)),
        Err(VerifyError::Rollback { .. })
    ));
    // security floor beats size
    assert!(matches!(
        verify_update(&m, &img[..10], &device(Version::new(3, 0, 0), 3)),
        Err(VerifyError::SecurityVersionTooLow { .. })
    ));
    // size beats chunk digests
    assert!(matches!(
        verify_update(&m, &img[..10], &device(Version::new(3, 0, 0), 1)),
        Err(VerifyError::SizeMismatch { expected: 6000, actual: 10 })
    ));
}
