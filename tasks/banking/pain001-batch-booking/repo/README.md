# payment-initiation-gateway

Inbound processing of customer payment files for the corporate channel
(host-to-host and EBICS uploads). This module turns ISO 20022
`pain.001.001.09` *CustomerCreditTransferInitiation* files into the internal
model, runs the pre-booking validation rules and hands accepted payment
batches to the booking engine.

## Layout

```
src/main/java/com/northbank/payments/
  pain/model/        immutable model of a pain.001 message
  pain/parser/       Pain001Parser (DOM, JDK built-in XML only)
  pain/validation/   PaymentValidator + IssueCode catalogue
  calendar/          TARGET2 business-day / cut-off calendar (used by scheduling)
src/test/java/       tests (tiny in-house runner in testkit/, no JUnit)
```

## Conventions

* Java 17, **no third-party dependencies** (the gateway runs in a locked-down
  runtime; only the JDK is available, including `javax.xml`).
* XML parsing must stay hardened: DOCTYPE declarations are rejected (XXE).
* Model classes are immutable; build them through their `Builder`.
* Validation never throws for business errors: it returns `ValidationIssue`s.
  `IssueCode` names are referenced by the operations runbook and the
  monitoring dashboards -- never rename existing codes.
* Parsing problems (malformed XML, missing mandatory elements, unparseable
  values) are reported with `ParseException` and the message names the
  offending element.
* Amounts are `BigDecimal`, never `double`.

## Running tests

```
./scripts/test.sh
```

Each test class is a plain class whose `@testkit.Test` methods are run by
`testkit.TestRunner`.
