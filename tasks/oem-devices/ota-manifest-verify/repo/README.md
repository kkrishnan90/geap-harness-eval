# ota-agent

Update agent running on the telematics control unit (TCU). It receives an
update manifest plus the image from the backend, verifies them, writes the
image to the inactive A/B slot and arms the bootloader to try it.

## Modules

| Module | Purpose |
| --- | --- |
| `manifest` | Parser for the line-based update manifest (see `docs/manifest-format.md`) |
| `version` | Firmware version numbers (`MAJOR.MINOR.PATCH`) |
| `verify` | Checks a manifest + image against the device state before install |
| `sha256` | Vendored SHA-256 (FIPS 180-4), no external crates allowed |
| `hex` | Hex encode/decode helpers |
| `slots` | A/B slot bookkeeping and boot-attempt counting |

## Conventions

* Rust 2021, **std only** — no crates from crates.io (the firmware build is offline).
* Errors are enums with explicit variants; never panic on input from the backend.
* Public items are used by the `tcu-daemon` crate; additive changes only.
* `cargo test --offline` must pass. Unit tests for internal helpers live next to the
  code; behaviour tests live in `tests/`.
