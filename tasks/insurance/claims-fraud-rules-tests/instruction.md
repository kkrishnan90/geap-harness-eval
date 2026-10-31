# SIU-412: Add a regression test suite for first-line fraud screening

**Component:** claims-screening (`fraud/FraudRulesEngine`) · **Type:** Task (test debt) · **Priority:** High

## Context

The Special Investigations Unit is about to tune the fraud rule weights and
thresholds. Today `FraudRulesEngine` is covered by a single smoke test, so
nobody can tell whether a change broke one of the rules in the SIU rule book.
Last quarter an "innocent" refactor silently turned an inclusive boundary into
an exclusive one and ~300 early claims skipped review.

Before the tuning work starts we need a test suite that pins down the current,
SIU-approved behaviour **exactly**, including every boundary.

## What to do

Create the test class
`src/test/java/com/harborline/claims/fraud/FraudRulesEngineTest.java`
(class `com.harborline.claims.fraud.FraudRulesEngineTest`) using the in-house
`testkit` (`@testkit.Test` public no-arg methods, `testkit.Assert`).

The suite must specify the behaviour in `docs/fraud-rules.md` (rule book
v2026.2, reproduced here) so that **any** deviation from it makes at least one
test fail:

| Rule | Weight | Fires when |
| --- | --- | --- |
| `EARLY_CLAIM` | 25 | Loss date is 0 to 30 days (inclusive) after policy inception. A loss before inception does not fire. |
| `HIGH_AMOUNT` | 20 | Claimed amount is at least 10,000.00. |
| `FREQUENT_CLAIMANT` | 30 | The same claimant has at least 3 prior claims with loss date on or after (loss date − 365 days) and strictly before this claim's loss date. A history entry with the same claim id as the screened claim is ignored. |
| `LATE_REPORTING` | 15 | Reported more than 60 days after the loss date. |
| `SHARED_BANK_ACCOUNT` | 40 | A prior claim of a different claimant used the same payout IBAN, compared ignoring spaces and letter case. |
| `ROUND_AMOUNT` | 5 | Amount ≥ 1,000.00 and an exact multiple of 1,000.00 (by value). |

Decision: claims under 500.00 are `AUTO_APPROVE` unless `SHARED_BANK_ACCOUNT`
fired; otherwise score ≥ 60 → `REFER_TO_SIU`, 30–59 → `MANUAL_REVIEW`,
below 30 → `AUTO_APPROVE`. `triggered()` lists fired rules in `RuleCode`
declaration order and `score()` is the sum of their weights.

## Acceptance criteria

- The class exists at the path above, compiles with the repo's testkit and
  contains at least 8 test methods.
- All its tests pass against the current engine.
- The suite catches regressions: a variant of `FraudRulesEngine` that breaks
  any single row of the rule book or the decision rules (e.g. an off-by-one
  boundary, a missed normalisation, a wrong comparison) must make at least one
  test fail.
- Tests are deterministic (no `LocalDate.now()`, no unseeded randomness, no
  sleeps) and finish in seconds.

## Constraints

- This is a test-only change: do **not** modify anything under
  `src/main/java` (the current engine is the reference behaviour).
- Keep the suite in that single file (nested helper classes/methods inside it
  are fine). Do not change `testkit`.
- Existing tests (`./scripts/test.sh`) must keep passing.
