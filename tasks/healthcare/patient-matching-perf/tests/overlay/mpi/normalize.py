"""Normalisation helpers shared by scoring and blocking."""

import re
import unicodedata

_NON_ALPHA = re.compile(r"[^A-Z]")
_SOUNDEX = {c: d for d, letters in {
    "1": "BFPV", "2": "CGJKQSXZ", "3": "DT", "4": "L", "5": "MN", "6": "R"}.items()
    for c in letters}


def name_key(value):
    """Upper-case ASCII letters only: "O'Brien-Smith" -> "OBRIENSMITH"."""
    if not value:
        return ""
    ascii_ = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return _NON_ALPHA.sub("", ascii_.upper())


def soundex(value):
    key = name_key(value)
    if not key:
        return ""
    out = key[0]
    last = _SOUNDEX.get(key[0], "")
    for ch in key[1:]:
        code = _SOUNDEX.get(ch, "")
        if code and code != last:
            out += code
        if ch not in "HW":
            last = code
    return (out + "000")[:4]


def phone_key(value):
    """Digits only, national format: "+44 (0)20 7946 0018" -> "2079460018"."""
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("44"):
        digits = digits[2:]
    digits = digits.lstrip("0")
    return digits if len(digits) >= 9 else ""


def postcode_key(value):
    return re.sub(r"\s", "", (value or "").upper())
