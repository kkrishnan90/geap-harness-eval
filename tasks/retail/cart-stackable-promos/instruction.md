# CART-882: Let promotions stack (priority, exclusivity groups, BOGO, per-line caps)

**Component:** `@storefront/pricing` · **Priority:** High · **Type:** Story

## Context

Today `priceCart()` applies only the single best promotion. Merchandising
wants to run campaigns that combine: a category discount plus a voucher, a
"buy 2 get 1 free" on T-shirts plus a site-wide percentage, and so on.
Marketing also needs "pick one of these" welcome offers, and finance wants a
cap per line on generous discounts. The checkout UI must be able to explain
every cent, so the result must contain a full breakdown.

## Model changes (`src/promotions.ts`)

Extend `Promotion` (keep all existing fields and their meaning):

| Field | Meaning |
| --- | --- |
| `kind: 'percent' \| 'fixed' \| 'bogo'` | new kind `bogo` |
| `buyQty?: number`, `getQty?: number` | for `bogo`: per eligible line, every complete group of `buyQty + getQty` units gives `getQty` units free |
| `priority?: number` | integer, default **100**; lower runs first within its phase |
| `exclusivityGroup?: string` | at most one promotion of the same group applies |
| `maxDiscountPerLineCents?: number` | cap on this promotion's discount on any single line (all kinds) |

`validatePromotion()` must accept `bogo` promotions with integer
`buyQty >= 1` and `getQty >= 1`.

## Pricing rules (`priceCart(cart, promotions)`)

1. **Minimum subtotal:** a promotion whose `minSubtotalCents` is above the cart
   subtotal (before any discount) is rejected with reason `MIN_SUBTOTAL`. It
   takes no further part (it does not compete in its exclusivity group).
2. **Exclusivity:** within each group, among the remaining promotions, keep the
   one with the largest *standalone* discount: the discount it would give if it
   were the only promotion on the undiscounted cart (cap included). Ties: lower
   `priority` number wins, then the smaller `id` (plain string comparison). The
   others are rejected with reason `EXCLUSIVITY`.
3. **Order of application:** all `bogo` promotions first, then all `percent`,
   then all `fixed`. Within a kind: `priority` ascending, then `id` ascending.
   The order of the input array does not matter.
4. **Stacking:** every promotion is applied to each eligible line's *current*
   amount (gross minus the discounts already given on that line by earlier
   promotions):
   - `bogo`: `floor(qty / (buyQty + getQty)) * getQty * unitPriceCents`
   - `percent`: `percentOf(current, percent)` (half-up rounding to the cent, per line)
   - `fixed`: `amountCents` per eligible line
   - then apply `maxDiscountPerLineCents` (if set), and never more than the
     line's current amount (a line never goes below 0).
5. A promotion whose total discount ends up 0 is not listed in `applied`; it is
   rejected with reason `NO_EFFECT`.

## Result shape

`PricedCart` keeps every existing field and gains `rejected`:

- `applied`: one entry per promotion that gave a discount, **in application
  order**: `{ promotionId, discountCents, lines: [{ sku, discountCents }] }`,
  where `lines` lists only lines with a non-zero discount from that promotion,
  in cart line order.
- `rejected`: `{ promotionId, reason: 'MIN_SUBTOTAL' | 'EXCLUSIVITY' | 'NO_EFFECT' }`,
  in the order the promotions were passed in.
- `lines[i].discountCents` is the total over all promotions; `netCents = grossCents - discountCents`.
- `discountCents` = sum of all line discounts; `totalCents = subtotalCents - discountCents`.

Export the new types (`RejectedPromotion`, `RejectionReason`) from `src/index.ts`.

## Example

Cart: JEANS 1 x 59.99 and T-shirts 3 x 15.00 (apparel). Promotions: 20% off
apparel (priority 200) and 5.00 off the jeans (priority 1). The percentage
runs first (phase order beats priority): jeans 59.99 -> -12.00 -> 47.99 ->
-5.00 -> 42.99; T-shirts -9.00.

## Acceptance criteria

- The rules above hold; results are deterministic and inputs are never mutated.
- A single promotion behaves exactly as before; all existing tests pass.

## Constraints

- Integer cents only; use the helpers in `src/money.ts`.
- No dependencies; erasable TypeScript only (Node 24 type stripping).
- Don't rename or remove existing exports or result fields.
