# TCU-OTA-812: Support manifest format 2 (anti-rollback + chunk digests)

**Component:** ota-agent · **Type:** Feature / Security · **Priority:** High
**Requested by:** Product Security (finding PSIRT-2026-044), OTA backend team

## Background

The update agent currently verifies an update with a single whole-image
SHA-256 (manifest format 1, see `docs/manifest-format.md`). Product Security
raised two findings:

1. **No rollback protection.** The agent installs any image whose digest
   matches, including older firmware with known vulnerabilities.
2. **No localisation of corruption.** Images arrive over flaky cellular links;
   when the whole-image digest fails we cannot tell which part to re-download.

The backend will start shipping **format 2** manifests next sprint. Format 1
manifests must keep working for the existing fleet.

## Manifest format 2

Same line syntax as format 1 (comments, blank lines, trimming, duplicate keys
rejected with `DuplicateKey`, unknown keys ignored). `format = 2` requires all
format 1 keys plus:

| Key | Value |
| --- | --- |
| `security_version` | anti-rollback counter, decimal `u32` |
| `chunk_size` | chunk length in bytes, decimal, must be > 0 |
| `chunk.<N>` | SHA-256 (64 hex chars) of chunk `N`; `N` is a decimal index starting at 0 |

Chunk `N` covers bytes `[N*chunk_size, min((N+1)*chunk_size, image_size))`; the
last chunk may be shorter. There must be exactly `ceil(image_size / chunk_size)`
chunk entries, indices `0..count-1`, in any order in the file.

```
format = 2
component = tcu-main
version = 6.0.0
security_version = 7
image_size = 10000
chunk_size = 4096
image_sha256 = <64 hex>
chunk.0 = <64 hex>
chunk.1 = <64 hex>
chunk.2 = <64 hex>
```

## Required API changes (additive; `tcu-daemon` depends on these names)

**`Manifest`** gets three public fields:
- `security_version: u32` — 0 for format 1
- `chunk_size: u64` — 0 for format 1
- `chunk_sha256: Vec<Digest>` — chunk digests ordered by index; empty for format 1

**`ManifestError`** gets two variants; parsing errors for format 2:
- missing `security_version` / `chunk_size` → `MissingKey("<key>")`
- non-decimal, negative or out-of-range (`> u32::MAX`) `security_version`,
  `chunk_size = 0`, non-numeric chunk index, or a malformed chunk digest →
  `InvalidValue { key, value }` (`key` is the offending key, e.g. `"chunk.1"`)
- `ChunkCountMismatch { expected: usize, found: usize }` — the number of
  `chunk.*` entries is not `ceil(image_size / chunk_size)`
- `MissingChunk(usize)` — the count is right but this index (the lowest
  missing one) has no entry
- any format other than 1 or 2 stays `UnsupportedFormat(n)`

**`Version`** must be totally ordered numerically (`4.10.0 > 4.9.0`) via
`PartialOrd`/`Ord`.

**`DeviceState`** gets `pub security_floor: u32` (the anti-rollback floor read
from secure storage). `DeviceState::new` keeps its signature and sets it to 0.

**`VerifiedUpdate`** gets `security_version: u32` and `chunks_verified: usize`
(number of chunk digests checked; 0 for format 1).

**`VerifyError`** gets:
- `Rollback { installed: Version, offered: Version }` — offered version is older than installed
- `AlreadyInstalled(Version)` — offered version equals installed
- `SecurityVersionTooLow { floor: u32, offered: u32 }` — `manifest.security_version < device.security_floor`
- `ChunkDigestMismatch { index: usize }` — lowest-index chunk whose digest differs

## Verification rules (`verify_update`)

Checks run in this order and the first failure is returned:

1. component (`ComponentMismatch`, unchanged)
2. version: `Rollback` / `AlreadyInstalled` — applies to format 1 and 2
3. `SecurityVersionTooLow` — applies to format 1 too (its security version is 0,
   so format 1 images are refused once a device's floor is above 0)
4. size (`SizeMismatch`, unchanged)
5. every chunk digest, in index order (`ChunkDigestMismatch`)
6. whole-image digest (`ImageDigestMismatch`, still checked for format 2)

## Constraints

- **std only, no external crates** (offline firmware toolchain); keep using the
  vendored `sha256` module.
- Additive changes only: do not rename or remove existing public items or variants.
- Never panic on manifest input.
- `cargo test --offline` must stay green.
