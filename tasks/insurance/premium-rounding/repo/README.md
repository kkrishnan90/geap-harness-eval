# motor-rating-core

Premium rating for Harborline private motor policies. The quote API, the
renewal batch and the mid-term-adjustment (MTA) service all call
`PremiumCalculator`; the result is printed on the policy schedule and the
instalment plan is sent to the direct-debit collector.

## Layout

```
src/main/java/com/harborline/motor/
  rating/   PremiumCalculator, RatingRequest, PremiumBreakdown, TaxTable
  policy/   Policy model, policy number generation
  claims/   excess (deductible) calculation used at FNOL
src/test/java/   tests (in-house runner in testkit/, no JUnit)
```

## Conventions

* Java 17, standard library only.
* Money is `BigDecimal` with scale 2 (pence). Never `double`.
* Pricing actuaries own the rounding rules (see "Rounding policy" in the
  pricing handbook, summarised in `PremiumCalculator`'s Javadoc). FCA rules
  require that the instalments shown to the customer add up exactly to the
  total payable.
* Public signatures are used by the quote API and must not change.

## Running tests

```
./scripts/test.sh
```
