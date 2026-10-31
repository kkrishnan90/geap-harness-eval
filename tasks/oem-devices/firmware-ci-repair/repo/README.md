# bootcfg-tools

Host + target library for the boot configuration block of the gateway ECU
bootloader (stage-2). The block is a sequence of TLV records protected by a
CRC-32; the bootloader, the flashing station and the end-of-line tester all
link `libbootcfg.a`.

## Modules

| File | Purpose |
| --- | --- |
| `include/bootcfg.h`, `src/tlv.c` | TLV record encoding/decoding of the boot configuration block |
| `include/fwver.h`, `src/fwver.c` | Firmware version strings (`MAJOR.MINOR.PATCH[-rcN]`) parse/compare |
| `include/crc32.h`, `src/crc32.c` | CRC-32 (IEEE 802.3, reflected) |
| `include/bootcfg_build.h`, `src/build_info.c` | Build tag baked into the library |

## Build

| Command | What it does |
| --- | --- |
| `make` / `make all` | Builds `build/libbootcfg.a` (objects in `build/obj/`) incrementally |
| `make test` | Builds and runs **every** `tests/test_*.c` as `build/test_*`; fails if any test fails |
| `make ci` | Clean build + all tests. This is exactly what the Jenkins pipeline runs (`ci/Jenkinsfile`) |
| `make clean` | Removes `build/` |

Rules for the build:

* Warnings policy: everything is compiled with `-std=c11 -Wall -Wextra -Werror`.
  Warnings are fixed in the code, never silenced (no `-Wno-*`, no pragmas).
* Incremental builds must be correct: changing a header rebuilds every object
  and test binary that depends on it.
* Toolchain on the CI agents: clang + GNU make 3.81 (macOS) / 4.x (Linux).

## Conventions

* C11, no dynamic allocation in `src/` (the library also builds for the
  target with arm-none-eabi-gcc).
* Public headers are frozen for this release; functions return
  `BOOTCFG_OK` (0) or a negative `BOOTCFG_ERR_*` code.
