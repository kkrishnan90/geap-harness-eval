# fleetroute

Line-haul planning library used by the Northline TMS (transport management
system). It turns a planned route (hubs + drive legs) into customer-facing
ETAs and dock-appointment times.

## Packages

| Package | Purpose |
| --- | --- |
| `internal/hubs` | Hub registry: IANA time zone and receiving window of every cross-dock / DC |
| `internal/eta` | ETA engine: drive time, statutory breaks, dwell, receiving windows |
| `internal/geo` | Great-circle distance and planned drive-time heuristics |
| `internal/manifest` | Trailer manifest: chargeable weight, load-metre utilisation |
| `cmd/etaplan` | CLI used by planners: `go run ./cmd/etaplan` |

## Conventions

* Go 1.22+, standard library only. Time zone data is embedded
  (`time/tzdata`) so results do not depend on the host.
* All instants are `time.Time` values; a hub's local time is only used for
  presentation and for local rules (receiving windows). Durations are real
  elapsed time (`time.Duration`).
* Public types and function signatures in `internal/eta` are used by the TMS
  adapter; do not change them.
* Tests: `go test ./...`
