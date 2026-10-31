# MOT-1883: Premiums off by a penny and instalment plans that don't add up

**Component:** motor-rating-core (`rating/`) · **Type:** Bug · **Priority:** High

## Context

Complaints and a compliance finding from the FCA consumer-duty review:

1. Schedules show a total payable that differs from the sum of the monthly
   direct debits (e.g. £100.00 over 6 months is collected as 6 × £16.67 =
   £100.02).
2. Pricing found quotes that are a penny higher or lower than the rating
   engine reference model, both on the net premium and on the Insurance
   Premium Tax (IPT) line.
3. Policies priced at the minimum premium show IPT that is far too low.

`PremiumCalculator` does not follow the rounding policy documented in its
own Javadoc (pricing handbook §4.2).

## Required behaviour (pricing handbook §4.2)

For `PremiumCalculator.calculate(RatingRequest)`:

1. **Net premium** = base rate × every rating factor, multiplied at full
   precision, then rounded **once** to pence with `HALF_EVEN` (banker's
   rounding). No intermediate rounding.
2. If the rounded net premium is below `minimumPremium`, the net premium is the
   minimum premium.
3. **Tax** = the final net premium (after steps 1–2) × the region's IPT rate
   (`TaxTable`), rounded to pence with `HALF_EVEN`.
4. **Gross premium** = net premium + tax.
5. **Instalments** (`PremiumCalculator.split(amount, n)` and the breakdown's
   `instalments()`): each instalment is `amount / n` rounded **down** to
   pence; the pence left over are added to the **first** instalment. The list
   has exactly `n` entries and always sums exactly to `amount`.

All amounts returned have scale 2.

## Examples

| Input | Expected |
| --- | --- |
| base 200.25, factors [0.5], GB | net 100.12, tax 12.01, gross 112.13 |
| base 100.00, factors [0.5], minimum 150.00, GB | net 150.00, tax 18.00 |
| split(100.00, 3) | [33.34, 33.33, 33.33] |
| split(100.00, 6) | [16.70, 16.66, 16.66, 16.66, 16.66, 16.66] |

## Constraints

- Do not change public signatures (`PremiumCalculator`, `RatingRequest`,
  `PremiumBreakdown`, `TaxTable`): the quote API depends on them.
- Java 17 standard library only; money stays `BigDecimal`.
- Existing tests (`./scripts/test.sh`) must keep passing.
