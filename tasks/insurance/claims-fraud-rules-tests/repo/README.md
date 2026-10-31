# claims-screening

Claims intake services for Harborline General: claim numbering, initial case
reserves and first-line fraud screening (`fraud/`). Screening results route a
claim to straight-through payment, a claims handler, or the Special
Investigations Unit (SIU).

## Layout

```
src/main/java/com/harborline/claims/
  model/     Claim (builder), PriorClaim, ClaimHistory
  fraud/     FraudRulesEngine, RuleCode (weights), Decision, FraudAssessment
  intake/    claim number format
  reserve/   initial reserve calculation
docs/fraud-rules.md   the SIU rule book the engine implements
src/test/java/        tests (in-house runner in testkit/, no JUnit)
```

## Conventions

* Java 17, standard library only.
* Tests are plain classes with `@testkit.Test` public no-arg methods, using
  `testkit.Assert`. A test class name ends in `Test`; `./scripts/test.sh`
  compiles and runs all of them.
* Tests must be deterministic: no wall clock (`LocalDate.now()`), no
  randomness without a fixed seed, no sleeps.
