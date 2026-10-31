"""BIC (ISO 9362) structural validation."""

import re
from dataclasses import dataclass
from typing import Optional

from .errors import ErrorCode

_BIC_RE = re.compile(r"^([A-Z]{4})([A-Z]{2})([A-Z0-9]{2})([A-Z0-9]{3})?$")


@dataclass(frozen=True)
class BicResult:
    valid: bool
    error: ErrorCode
    institution: Optional[str] = None
    country: Optional[str] = None
    location: Optional[str] = None
    branch: Optional[str] = None


def validate_bic(raw, expected_country=None):
    if not raw or not raw.strip():
        return BicResult(False, ErrorCode.EMPTY)
    bic = raw.strip().upper()
    m = _BIC_RE.match(bic)
    if not m:
        return BicResult(False, ErrorCode.INVALID_BIC)
    inst, country, loc, branch = m.groups()
    # A "test BIC" has '0' as second location character; not allowed in production.
    if loc[1] == "0":
        return BicResult(False, ErrorCode.INVALID_BIC)
    if expected_country and country != expected_country:
        return BicResult(False, ErrorCode.BIC_COUNTRY_MISMATCH, inst, country, loc, branch)
    return BicResult(True, ErrorCode.OK, inst, country, loc, branch or "XXX")
