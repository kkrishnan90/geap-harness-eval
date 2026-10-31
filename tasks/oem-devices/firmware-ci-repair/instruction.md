# BLDR-982: `bootcfg-tools` pipeline red since the Makefile cleanup

**Component:** bootcfg-tools build (`Makefile`) · **Priority:** High · **Type:** CI

## Context

The Jenkins job for `bootcfg-tools` only runs `make ci` (see `ci/Jenkinsfile`).
Since last week's "Makefile cleanup" commit the job is red, and while looking
at it we found that the build had been lying to us for a while:

- `make ci` now fails right away (headers not found).
- The `test` target reports "all tests passed" without running anything, and
  even when a test binary runs, a failing test does not fail the build.
- After editing a header, `make test` keeps using stale objects (a release
  build shipped with the previous `BOOTCFG_BUILD_TAG`).

Once the include path is fixed you will also hit a `-Werror` failure. That
warning points at a real defect in the TLV decoder and must be fixed **in the
code** — see the README warnings policy.

## Expected behaviour (see README "Build")

1. `make ci` from a clean checkout exits 0: it does a clean build of
   `build/libbootcfg.a` and builds and runs **every** `tests/test_*.c`
   (as `build/test_*`, linked against the library). Tests added later with
   that naming are picked up automatically.
2. If any test binary exits non-zero, `make test` / `make ci` exit non-zero.
3. `make test` is incremental and correct: after changing any header under
   `include/`, every object and test binary that depends on it is rebuilt.
4. All objects are still compiled with `-std=c11 -Wall -Wextra -Werror`;
   no warnings are disabled (no `-Wno-*`, `-w`, or diagnostic pragmas).
5. `bootcfg_tlv_next()` must never read past `len`: a record whose header
   (type + length byte) or value does not fit in the remaining bytes returns
   `BOOTCFG_ERR_TRUNCATED` and leaves `*off` at the start of that record
   (PAD bytes before it are still skipped). `bootcfg_verify()` propagates
   that error for a block that is cut inside a record.

## Constraints

- Keep the target names (`all`, `test`, `ci`, `clean`) and the `build/`
  output layout; must work with GNU make 3.81 (macOS) and clang.
- Do not change public headers.
