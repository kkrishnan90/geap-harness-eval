# mdm-vee

Validation, Estimation and Editing (VEE) for 15-minute interval data from
smart meters, as run by the meter data management (MDM) pipeline before data
is released to billing and settlement.

| Package | Purpose |
| --- | --- |
| `internal/interval` | `Reading` type, CSV decoding of head-end exports |
| `internal/vee` | Validation rules (`Validate`) and gap estimation (`Estimate`) |
| `internal/obis` | OBIS code parsing (IEC 62056-61) for register mapping |
| `cmd/vee-run` | Runs VEE over a CSV export and prints the issues |

## Conventions

* Go 1.22, standard library only. All times are UTC.
* Energy values are integer watt-hours (Wh). No floating point.
* VEE rules are specified in `docs/vee-rules.md`; every rule must be covered
  by unit tests in `internal/vee`.
* Tests: `go test ./...`
