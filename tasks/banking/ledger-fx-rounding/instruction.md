# GLT-883: Month-end trial balance off by cents after FX revaluation

**Component:** treasury-ledger · **Type:** Bug · **Priority:** Critical (blocks January close)

## Context

Group consolidation rejected the January trial balance of the treasury book:
total debits and total credits differ by a few cents in EUR. The difference
appears after `RevaluationService` runs on the foreign-currency nostro and
deposit accounts, and grows with every month-end. On some days the close even
aborts with an `UnbalancedEntryException` from the revaluation itself.

Finance also reports that individual converted amounts do not match their
reference calculations, e.g.

- 1,000,000.00 USD booked at EUR/USD 1.0850 shows **921,659.00 EUR**; the
  correct value is 1,000,000.00 / 1.0850 = **921,658.99 EUR**.
- 1.00 EUR at EUR/USD 1.0850 shows **1.09 USD**; policy FP-07 (banker's
  rounding) requires **1.08 USD**.
- A USD account that was emptied during the month still carries a small EUR
  value after the close.

## Expected behaviour (finance policy FP-07 / IAS 21)

1. **Rounding.** Every rounding of a monetary amount to its currency's minor
   unit (`Currency#getDefaultFractionDigits`, e.g. EUR 2, JPY 0, KWD 3) uses
   round-half-even. `Rounding.MODE` is the single place that defines it.
2. **Conversion.** `FxConverter.convert` computes exactly with `BigDecimal`
   and rounds once, at the end, to the target currency's minor unit:
   - if the table has a direct quote `from/to`, multiply by it;
   - if it only has the reverse quote `to/from` (the normal case, Treasury
     publishes one direction per pair), **divide** by that quote using
     `MathContext.DECIMAL128` (do not multiply by a pre-rounded inverse).
   - `RateTable.rate(from, to)` for a derived reverse rate must be accurate to
     at least 20 significant digits (e.g. `1 / quote` with `DECIMAL128`).
   No money or rate value may go through `double`.
3. **Double entry is strict.** `Ledger.post` must reject any entry whose
   functional-currency debits and credits differ at all (not even 0.01 is
   tolerated), with `UnbalancedEntryException`, leaving the ledger unchanged.
4. **Revaluation.** For each foreign-currency ASSET/LIABILITY account,
   the target functional value is the account balance converted at the
   closing rates (rule 2). The adjustment is
   `delta = target - carried functional balance`; when `delta != 0`, post one
   entry with exactly two lines: the account (side DEBIT if `delta > 0`,
   otherwise CREDIT, account-currency amount zero, functional `|delta|`) and
   the FX result account on the opposite side with `|delta|` EUR. Both lines
   carry the same amount, so the entry always balances.
   - An account whose foreign balance is zero but which still carries a
     functional balance must be revalued too (its functional value is cleared
     to zero). Accounts with no balance at all are skipped and need no closing
     rate.
   - Keep the current entry ids, ordering (account order) and return value.

## Acceptance criteria

- After any sequence of bookings and month-end revaluations, every journal
  entry balances exactly and `TrialBalance.isBalanced()` is true.
- After a revaluation, each revalued account's functional balance equals its
  balance converted at the closing rates (rule 2).
- The examples above produce the correct values.
- All existing tests pass (`./scripts/test.sh`).

## Constraints

- Do not change public class names or method signatures; existing callers
  (consolidation export, statement printing) must keep compiling.
- JDK only, Java 17.
