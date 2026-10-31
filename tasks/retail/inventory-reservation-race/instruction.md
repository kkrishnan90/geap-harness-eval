# SHOP-2291: Flash sale oversold limited stock (concurrent checkout race)

**Component:** northwind-commerce-core / inventory · **Priority:** Blocker · **Type:** Bug

## Context

During Friday's console flash sale we sold 1,312 units of a SKU that had 400
units on hand. The warehouse had to cancel ~900 paid orders. Post-incident
analysis showed it is not a data-entry problem: `ReservationService` is called
by 64 checkout worker threads per pod and its stock updates are a plain
load → check → modify → save sequence on detached copies from the
`InventoryRepository`. Concurrent calls for the same SKU overwrite each other.

We also saw in the audit trail:

- the same order line holding two or more reservations after the payment
  gateway retried `reserve` for an order (retries are expected and must be
  idempotent),
- a single reservation being released several times by the expiry job and
  the payment-failure handler racing each other (each release returned `true`
  and gave the units back again),
- goods receipts (`restock`) that disappeared when booked at the same time as
  sales.

## Expected behaviour

Under any interleaving of concurrent calls to `reserve`, `release`, `commit`
and `restock`, `ReservationService` must behave as if the calls for a given
SKU happened one at a time:

1. `available` (`onHand - reserved`) never becomes negative; a reservation
   succeeds only if enough units are available at that moment, otherwise it
   throws `InsufficientStockException` and changes nothing.
2. The stored `reserved` value always equals the sum of quantities of the
   SKU's active reservations (`activeReservations(sku)`), and `onHand` reflects
   every `commit` and `restock` exactly once.
3. `reserve(orderId, sku, qty)` stays idempotent per (orderId, sku) even when
   retries arrive concurrently: exactly one reservation is created and every
   caller gets that same reservation.
4. `release` / `commit` of the same reservation called concurrently: exactly
   one call wins and returns `true`, the others return `false`; stock and the
   audit log are updated once.
5. **No global lock.** We have ~40k SKUs in a sale; operations on *different*
   SKUs must never wait for each other (no service-wide lock, no
   `synchronized` service methods, no lock striping that can make two SKUs
   share a lock). In particular, a reservation for SKU B must complete while a
   reservation for SKU A is still in progress (e.g. stuck in a slow
   repository call).

## Acceptance criteria

- The behaviours above hold for the in-memory repository and for any correct
  `InventoryRepository` implementation (the JDBC adapter has the same
  semantics: atomic per-record operations, `load` returns detached copies).
- Existing tests (`scripts/test.sh`) keep passing; single-threaded behaviour
  is unchanged.

## Constraints

- Do not change the `InventoryRepository` interface or the public signatures
  of `ReservationService`, `CheckoutService`, `StockRecord`, `Reservation`.
- Java 17 standard library only. No sleeps/retries-with-delay as a "fix".
