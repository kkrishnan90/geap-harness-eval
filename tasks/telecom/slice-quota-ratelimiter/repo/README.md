# pcf-quota

Policy-control helpers for the 5G core PCF: per network-slice (S-NSSAI) quota
enforcement on the user-plane admission path, slice policy loading, and
charging-ID allocation.

## Layout

| Package | Purpose |
| --- | --- |
| `internal/snssai` | S-NSSAI value type (`SST[-SD]`, TS 23.003 §28.4.2) |
| `internal/clock` | `Clock` interface + deterministic `Fake` clock for tests |
| `internal/quota` | Slice quota specs (and the limiter, see PCF-2210) |
| `internal/policy` | Loads slice policies from JSON (`configs/slices.json`) |
| `internal/chargingid` | Charging ID allocation (TS 32.298) |
| `cmd/quota-sim` | Replays an admission trace against the configured quotas |

## Conventions

* Go 1.22, standard library only, no network access in tests.
* Nothing on the admission path may call `time.Now()` directly: take a
  `clock.Clock` so tests can drive time with `clock.Fake`.
* Quota amounts are integers (bytes or tokens). No floating point on the
  admission path; rounding must be exact and reproducible across nodes.
* Everything exported from `internal/quota` must be safe for concurrent use.
* Tests: `go test ./...`
