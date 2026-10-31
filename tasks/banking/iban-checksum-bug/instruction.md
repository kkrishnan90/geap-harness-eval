# PAY-4127: Valid IBANs rejected when typed in lowercase or with spaces

**Component:** payments-core (`payments_core/iban.py`) · **Priority:** High · **Type:** Bug

## Context

`validate_iban()` is used by the online-banking channel and the bulk-upload
importer to check every debtor and creditor account before a SEPA credit
transfer is submitted. Since the new mobile app went live, the repair queue is
filling up with transfers flagged `INVALID_CHARACTERS` / `INVALID_CHECKSUM`
for accounts that are perfectly valid. Customers copy IBANs from invoices in
paper format (`DE89 3704 0044 0532 0130 00`) or type them in lowercase.

While investigating, the payments ops team also found the opposite problem:
some IBANs that are **longer** than their country allows, and IBANs from
countries that do not use IBAN at all, are accepted.

## Expected behaviour

`validate_iban(raw)` must:

1. Ignore leading/trailing whitespace and any number of ASCII space characters
   between the characters of the IBAN. No other separator is allowed (hyphens,
   dots, tabs or other characters inside the IBAN stay `INVALID_CHARACTERS`).
2. Be case-insensitive. `IbanResult.normalized` is the electronic format:
   upper case, no spaces. `IbanResult.country` is the upper-case country code.
3. Reject a country code that is not in the registry
   (`payments_core/registry.py`) with `ErrorCode.UNKNOWN_COUNTRY`
   (with `country` set on the result).
4. Require the length to be **exactly** the registered length for the country,
   otherwise `ErrorCode.INVALID_LENGTH` (with `country` set), even when the
   check digits happen to be valid.
5. Only then verify the ISO 7064 mod-97 check (`INVALID_CHECKSUM`).

`normalize_iban(raw)` must return the same electronic format as
`IbanResult.normalized`, and `format_iban()` must work for any input that
`validate_iban()` accepts.

## Acceptance criteria

- `validate_iban("gb82 west 1234 5698 7654 32")` is valid, normalized
  `GB82WEST12345698765432`.
- `validate_iban("NO37860111179470")` (16 characters, Norway is 15) returns
  `INVALID_LENGTH`.
- `validate_iban("ZZ1812345678901234")` returns `UNKNOWN_COUNTRY`.
- SEPA `precheck()` accepts transfers whose IBANs were typed in paper format.
- All existing tests keep passing.

## Constraints

- Do not change public function signatures or `ErrorCode` names/values (the
  gateway persists them).
- Standard library only.
- Run the tests with `python3 -m unittest discover -s tests -t .`
