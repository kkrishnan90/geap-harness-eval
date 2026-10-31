# brightmart-loyalty

Points ledger, tier management and e-statements for BrightMart Rewards
(~11M members in the UK, Ireland and — since the 2026 acquisition — Australia
and Japan).

## Layout

```
src/main/java/com/brightmart/loyalty/
  model/       Member, PointsEntry, Category
  points/      EarnRules, PointsExpiryPolicy, PointsBalance
  tier/        Tier, TierService (thresholds, anniversary re-assessment)
  statement/   StatementFormatter (e-statement lines; runs in a worker pool)
  catalog/     RewardCatalog
src/test/java/ tests (in-house runner in testkit/, no JUnit)
```

## Conventions

* Java 17, standard library only.
* Domain dates are evaluated in the **member's home time zone** (a member in
  Tokyo who shops at 08:00 local time on 1 April earned the points on
  1 April, whatever the server's zone).
* Never depend on the JVM default time zone or locale.
* `./scripts/test.sh` compiles and runs every `*Test` class.
