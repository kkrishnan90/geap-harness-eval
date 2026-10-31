# payments-core

Shared validation and formatting helpers used by the SEPA payment-initiation
services (channel gateway, bulk upload, and the back-office repair queue).

## Layout

| Module | Purpose |
| --- | --- |
| `payments_core/iban.py` | IBAN normalisation, ISO 13616 mod-97 validation, print formatting |
| `payments_core/bic.py` | BIC / SWIFT code structure checks (ISO 9362) |
| `payments_core/registry.py` | Country registry: IBAN lengths, SEPA membership |
| `payments_core/sepa.py` | SEPA credit transfer pre-validation (amount, currency, parties) |
| `payments_core/errors.py` | Error codes shared with the channel gateway (do not renumber) |

## Conventions

* Python 3.11+, standard library only (this package is vendored into services
  that cannot take third-party dependencies).
* Public functions keep their signatures; the channel gateway maps
  `ErrorCode` values to user-facing messages, so codes must not be renamed.
* Validators never raise on bad user input: they return a result object.
* Tests use `unittest`:

```
python3 -m unittest discover -s tests -t .
```
