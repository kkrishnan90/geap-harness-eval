"""IBAN handling (ISO 13616).

`validate_iban` is called for every debtor/creditor account entered in the
online banking channels and for every row of a bulk upload file, so it must
accept what customers actually type (see README "Conventions").
"""

from dataclasses import dataclass
from typing import Optional

from .errors import ErrorCode
from .registry import iban_length

@dataclass(frozen=True)
class IbanResult:
    valid: bool
    error: ErrorCode
    normalized: Optional[str] = None
    country: Optional[str] = None

    def __bool__(self):
        return self.valid


def normalize_iban(raw):
    """Return the electronic format of an IBAN (no separators, upper case)."""
    return "".join(raw.strip().split(" ")).upper()


def _to_digits(iban):
    """Move the first four characters to the end and convert letters (A=10 ... Z=35)."""
    rearranged = iban[4:] + iban[:4]
    out = []
    for ch in rearranged:
        if ch.isdigit():
            out.append(ch)
        else:
            out.append(str(ord(ch) - 55))
    return "".join(out)


def _mod97(digits):
    # Piecewise reduction keeps intermediate values small (as in ISO 7064).
    remainder = 0
    for start in range(0, len(digits), 9):
        remainder = int(str(remainder) + digits[start:start + 9]) % 97
    return remainder


def validate_iban(raw):
    """Validate an IBAN as typed by a user. Never raises for bad input."""
    if raw is None or not str(raw).strip():
        return IbanResult(False, ErrorCode.EMPTY)

    iban = normalize_iban(str(raw))
    if not iban.isalnum() or not iban.isascii():
        return IbanResult(False, ErrorCode.INVALID_CHARACTERS)

    country = iban[:2]
    if not country.isalpha() or not iban[2:4].isdigit():
        return IbanResult(False, ErrorCode.INVALID_CHARACTERS)

    expected = iban_length(country)
    if expected is None:
        return IbanResult(False, ErrorCode.UNKNOWN_COUNTRY, country=country)
    if len(iban) != expected:
        return IbanResult(False, ErrorCode.INVALID_LENGTH, country=country)

    if _mod97(_to_digits(iban)) != 1:
        return IbanResult(False, ErrorCode.INVALID_CHECKSUM, country=country)

    return IbanResult(True, ErrorCode.OK, normalized=iban, country=country)


def format_iban(raw):
    """Paper format: groups of four separated by single spaces.

    Raises ValueError if the IBAN is not valid (callers format only validated data).
    """
    result = validate_iban(raw)
    if not result.valid:
        raise ValueError(f"cannot format invalid IBAN: {result.error.name}")
    s = result.normalized
    return " ".join(s[i:i + 4] for i in range(0, len(s), 4))
