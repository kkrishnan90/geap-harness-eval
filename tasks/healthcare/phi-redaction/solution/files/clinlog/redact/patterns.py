"""Replacement token, PHI key/field maps and free-text PHI patterns."""

import re
from typing import List, Optional, Tuple

CATEGORIES = ("NAME", "MRN", "DOB", "SSN", "PHONE", "EMAIL", "ADDRESS")


def token(category: str) -> str:
    """Replacement token for a redacted value, e.g. ``[PHI:NAME]``."""
    if category not in CATEGORIES:
        raise ValueError(f"unknown PHI category {category!r}")
    return f"[PHI:{category}]"


# --- structured keys (JSON keys and key=value keys) -------------------------

_KEY_CATEGORIES = {
    "NAME": ("patientname", "firstname", "lastname", "givenname", "familyname", "fullname", "maidenname"),
    "MRN": ("mrn", "patientid", "medicalrecordnumber"),
    "DOB": ("dob", "dateofbirth", "birthdate"),
    "SSN": ("ssn", "socialsecuritynumber"),
    "PHONE": ("phone", "phonenumber", "mobile", "homephone"),
    "EMAIL": ("email", "emailaddress"),
    "ADDRESS": ("address", "streetaddress", "street", "postalcode", "zip", "zipcode"),
}
KEY_CATEGORY = {k: cat for cat, keys in _KEY_CATEGORIES.items() for k in keys}


def normalize_key(key: str) -> str:
    return key.lower().replace("_", "").replace("-", "")


def key_category(key: str) -> Optional[str]:
    return KEY_CATEGORY.get(normalize_key(key))


# --- HL7 fields ---------------------------------------------------------------

HL7_FIELDS = {
    "PID": {3: "MRN", 5: "NAME", 6: "NAME", 7: "DOB", 11: "ADDRESS", 13: "PHONE", 14: "PHONE", 19: "SSN"},
    "NK1": {2: "NAME", 4: "ADDRESS", 5: "PHONE"},
}

# --- free text ------------------------------------------------------------------

SSN_RE = re.compile(r"(?<![\w-])\d{3}-\d{2}-\d{4}(?![\w-])")
MRN_RE = re.compile(r"(?i)\bMRN[:#]?\s?\d{7}(?!\d)")
EMAIL_RE = re.compile(r"(?<![\w.+%-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}(?!\w)")
PHONE_RE = re.compile(r"(?<![\w-])(?:\+1[ .-]?)?(?:\(\d{3}\) ?|\d{3}[-.])\d{3}[-.]\d{4}(?![\w-])")
DOB_RE = re.compile(r"(?i)\b(?:DOB|date of birth|born)\s*[:=]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})(?!\d)")

_TEXT_PATTERNS = (("SSN", SSN_RE, 0), ("MRN", MRN_RE, 0), ("EMAIL", EMAIL_RE, 0),
                  ("PHONE", PHONE_RE, 0), ("DOB", DOB_RE, 1))


def find_spans(text: str) -> List[Tuple[int, int, str]]:
    """Non-overlapping (start, end, category) spans, leftmost first, longer wins ties."""
    found = []
    for cat, rx, group in _TEXT_PATTERNS:
        for m in rx.finditer(text):
            found.append((m.start(group), m.end(group), cat))
    found.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    chosen, last_end = [], -1
    for start, end, cat in found:
        if start >= last_end:
            chosen.append((start, end, cat))
            last_end = end
    return chosen


def scrub_text(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Redact free-text PHI. Returns (new_text, [(category, original), ...])."""
    spans = find_spans(text)
    if not spans:
        return text, []
    out, hits, pos = [], [], 0
    for start, end, cat in spans:
        out.append(text[pos:start])
        out.append(token(cat))
        hits.append((cat, text[start:end]))
        pos = end
    out.append(text[pos:])
    return "".join(out), hits
