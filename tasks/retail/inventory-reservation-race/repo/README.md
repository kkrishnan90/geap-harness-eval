# northwind-commerce-core

Order-capture core of the Northwind web shop: catalogue lookup, basket pricing,
and stock reservation for checkout. Deployed inside the `checkout-api` service
(Java 17), which runs 64 checkout worker threads per pod.

## Modules

| Package | Purpose |
| --- | --- |
| `com.northwind.commerce.catalog` | Product catalogue (read-mostly, refreshed nightly from PIM) |
| `com.northwind.commerce.pricing` | Line totals, VAT extraction |
| `com.northwind.commerce.inventory` | Stock records, repository port, reservations, audit trail |
| `com.northwind.commerce.checkout` | Basket model and all-or-nothing checkout |

### Inventory model

* `StockRecord`: `onHand` (physically in the node) and `reserved` (promised to
  open orders). `available = onHand - reserved` and must never be negative.
* `InventoryRepository` is the storage port. Production uses the JDBC adapter
  (`northwind-inventory-jdbc`, Fulfilment team) behind a Redis cache; the
  `InMemoryInventoryRepository` here mimics that cache (records are stored
  serialized, every `load` returns a detached copy). The port supports
  optimistic locking via `saveIfVersion`.
* `ReservationService` is the only component that mutates stock records.
  Lifecycle: `reserve` -> `commit` (picked/shipped) or `release` (payment
  failed / hold expired). `restock` books goods receipts.

## Conventions

* Java 17, no third-party dependencies. There is no Maven/Gradle in the build
  sandbox; tests use the tiny in-repo `testkit` (`@testkit.Test`, `testkit.Assert`).
* Run tests: `scripts/test.sh` (optionally `scripts/test.sh ReservationServiceTest`).
* Public method signatures of `ReservationService`, `CheckoutService` and the
  `InventoryRepository` interface are consumed by other teams: don't change them.
* Money is `BigDecimal`; quantities are `int`.
