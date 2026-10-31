# @storefront/pricing

Prices a shopping cart for the web shop and the mobile app checkout:
promotions, VAT and shipping. Consumed by `checkout-api` (server side) and
by the basket preview in the app (same code, bundled).

## Layout

| File | Purpose |
| --- | --- |
| `src/money.ts` | Integer-cent helpers and rounding (never use floats for money) |
| `src/cart.ts` | Cart and line model, subtotal |
| `src/promotions.ts` | Promotion model, eligibility and per-kind discount calculation |
| `src/engine.ts` | `priceCart()` - applies promotions and builds the priced cart |
| `src/tax.ts` | VAT breakdown per rate (prices are VAT-inclusive) |
| `src/shipping.ts` | Shipping fee rules and free-shipping threshold |
| `src/index.ts` | Public entry point (only import from here outside this package) |

## Conventions

* Node 24, TypeScript executed directly via type stripping: only erasable
  syntax (no `enum`, `namespace`, parameter properties). No dependencies.
* All money is **integer cents** (`number`, always a safe integer).
  Percentages are integers. Rounding goes through `src/money.ts`.
* `priceCart()` is pure: same input, same output; it never mutates its input.
* The JSON shape returned by `priceCart()` is rendered by the checkout UI;
  adding fields is fine, renaming or removing fields is a breaking change.
* Tests: `npm test` (or `node --test test/*.test.ts`).
