# policy-import

Broker-portal back end for the **legacy batch upload**: brokers that still run
the old policy-admin system (PAS) upload their nightly policy batches, which are
validated and stored in the policy repository.

## Layout

| Package | Purpose |
| --- | --- |
| `com.meridianre.policy.model` | Wire model shared with PAS (`PolicyBatch`, `Policy`, `Party`, `Coverage`, enums) |
| `com.meridianre.policy.io` | `PolicyImporter` (upload -> `PolicyBatch`), `PolicyExporter` (DR replication) |
| `com.meridianre.policy.service` | `ImportService` use case, `PolicyValidator` business rules, `ImportReport` |
| `com.meridianre.policy.repo` | In-memory policy repository (prod adapter lives elsewhere) |
| `com.meridianre.policy.rating` | Technical premium calculation |

## Conventions

* Java 17, JDK only (no Maven/Gradle in this container; no third-party libraries).
* The wire format is Java serialization of `PolicyBatch` (PAS v4 layout). The
  model classes' `serialVersionUID`s are frozen: PAS writes them.
* Upload failures are reported, never thrown: `ImportService.upload` returns an
  `ImportReport` and writes an audit line `"<broker> REJECTED <reason>"` or
  `"<broker> IMPORTED ..."`.
* Tests use the tiny `testkit` harness (`@Test`, `Assert`):

```
scripts/test.sh
```
