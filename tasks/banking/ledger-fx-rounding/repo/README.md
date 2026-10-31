# treasury-ledger

General ledger used by Meridian Treasury Services for nostro accounts and
customer deposits held in foreign currencies. The functional (reporting)
currency is EUR. Month-end close runs `RevaluationService` with the ECB-based
closing rates published by Treasury, then exports the `TrialBalance` to group
consolidation.

## Modules

| Package | Purpose |
| --- | --- |
| `money` | `Money` value type and the group **rounding policy** (`Rounding`) |
| `fx` | `FxRate` quotes, `RateTable` (one per booking/closing date), `FxConverter` |
| `core` | accounts, journal entries, `Ledger` (posting rules, balances), `EntryBuilder` |
| `reval` | month-end FX revaluation of monetary accounts (IAS 21) |
| `report` | `TrialBalance`, plain-text `StatementFormatter` |
| `coa` | chart-of-accounts CSV loader |

## Accounting conventions

* **Double entry is an invariant**: every journal entry has exactly equal debit
  and credit totals in functional currency. Group consolidation rejects a trial
  balance that is off by even one cent.
* Balances are debit-positive. Posting amounts are non-negative; the side gives
  the sign.
* Amounts are `BigDecimal`. Never route money or rates through `double`.
* Rounding to a currency's minor unit (`Currency#getDefaultFractionDigits`:
  EUR 2, JPY 0, KWD 3) uses the group policy in `money/Rounding`, which is
  **banker's rounding** (round half to even) per the finance policy FP-07.
* Treasury publishes each currency pair once, in market convention
  (EUR/USD, EUR/JPY, GBP/EUR ...). Conversions in the other direction are
  derived from that quote.
* Cross-currency entries between two foreign currencies are not supported;
  route them through a EUR clearing account.

## Building and testing

Java 17, JDK only (no Maven/Gradle in the build container).

```
./scripts/test.sh
```

Tests are plain classes with `@testkit.Test` methods, run by
`testkit.TestRunner` (see `src/test/java/testkit`).
